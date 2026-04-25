use crate::ux_sanity::issue::Issue;
use crate::ux_sanity::parser::{offset_to_line_col, ParsedFile};
use oxc_ast::ast::{Statement, BindingPattern, Expression, Declaration, ExportDefaultDeclarationKind};
use std::collections::HashSet;

/// Finds `setState()` calls directly in component body (not in handler/effect).
pub fn check(parsed: &ParsedFile, file: &str) -> Vec<Issue> {
    let mut issues = Vec::new();

    for stmt in &parsed.program.body {
        scan_top_level(stmt, parsed.source, file, &mut issues);
    }

    issues
}

fn scan_top_level(stmt: &Statement, source: &str, file: &str, issues: &mut Vec<Issue>) {
    match stmt {
        Statement::FunctionDeclaration(fd) => {
            if is_component_name(fd.id.as_ref().map(|i| i.name.as_str())) {
                if let Some(body) = &fd.body {
                    analyze_component_body(&body.statements, source, file, issues);
                }
            }
        }
        Statement::VariableDeclaration(vd) => {
            for decl in &vd.declarations {
                let name = if let BindingPattern::BindingIdentifier(id) = &decl.id {
                    Some(id.name.as_str())
                } else {
                    None
                };
                if !is_component_name(name) {
                    continue;
                }
                let Some(init) = &decl.init else { continue };
                match init {
                    Expression::ArrowFunctionExpression(af) => {
                        analyze_component_body(&af.body.statements, source, file, issues);
                    }
                    Expression::FunctionExpression(fe) => {
                        if let Some(b) = &fe.body {
                            analyze_component_body(&b.statements, source, file, issues);
                        }
                    }
                    _ => {}
                }
            }
        }
        Statement::ExportNamedDeclaration(en) => {
            if let Some(decl) = &en.declaration {
                if let Declaration::FunctionDeclaration(fd) = decl {
                    if is_component_name(fd.id.as_ref().map(|i| i.name.as_str())) {
                        if let Some(body) = &fd.body {
                            analyze_component_body(&body.statements, source, file, issues);
                        }
                    }
                }
                if let Declaration::VariableDeclaration(vd) = decl {
                    for d in &vd.declarations {
                        let name = if let BindingPattern::BindingIdentifier(id) = &d.id {
                            Some(id.name.as_str())
                        } else {
                            None
                        };
                        if !is_component_name(name) {
                            continue;
                        }
                        if let Some(init) = &d.init {
                            match init {
                                Expression::ArrowFunctionExpression(af) => {
                                    analyze_component_body(&af.body.statements, source, file, issues);
                                }
                                Expression::FunctionExpression(fe) => {
                                    if let Some(b) = &fe.body {
                                        analyze_component_body(&b.statements, source, file, issues);
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
        Statement::ExportDefaultDeclaration(ed) => {
            if let ExportDefaultDeclarationKind::FunctionDeclaration(fd) = &ed.declaration {
                if let Some(body) = &fd.body {
                    analyze_component_body(&body.statements, source, file, issues);
                }
            }
        }
        _ => {}
    }
}

fn is_component_name(name: Option<&str>) -> bool {
    name.and_then(|n| n.chars().next()).is_some_and(|c| c.is_ascii_uppercase())
}

fn analyze_component_body(stmts: &[Statement], source: &str, file: &str, issues: &mut Vec<Issue>) {
    let mut setters: HashSet<String> = HashSet::new();
    for stmt in stmts {
        collect_setters(stmt, &mut setters);
    }
    if setters.is_empty() {
        return;
    }

    for stmt in stmts {
        scan_for_setter_calls(stmt, &setters, source, file, issues);
    }
}

fn collect_setters(stmt: &Statement, setters: &mut HashSet<String>) {
    if let Statement::VariableDeclaration(vd) = stmt {
        for decl in &vd.declarations {
            let Some(init) = &decl.init else { continue };
            let Expression::CallExpression(ce) = init else { continue };
            let is_usestate = match &ce.callee {
                Expression::Identifier(id) => id.name.as_str() == "useState",
                Expression::StaticMemberExpression(sme) => sme.property.name.as_str() == "useState",
                _ => false,
            };
            if !is_usestate {
                continue;
            }
            if let BindingPattern::ArrayPattern(arr) = &decl.id {
                if arr.elements.len() >= 2 {
                    if let Some(second) = &arr.elements[1] {
                        if let BindingPattern::BindingIdentifier(id) = second {
                            setters.insert(id.name.to_string());
                        }
                    }
                }
            }
        }
    }
}

fn scan_for_setter_calls(
    stmt: &Statement,
    setters: &HashSet<String>,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    match stmt {
        Statement::ExpressionStatement(es) => {
            check_setter_call(&es.expression, setters, source, file, issues);
        }
        Statement::IfStatement(is) => {
            scan_for_setter_calls(&is.consequent, setters, source, file, issues);
            if let Some(a) = &is.alternate {
                scan_for_setter_calls(a, setters, source, file, issues);
            }
        }
        Statement::BlockStatement(bs) => {
            for s in &bs.body {
                scan_for_setter_calls(s, setters, source, file, issues);
            }
        }
        _ => {}
    }
}

fn check_setter_call(
    expr: &Expression,
    setters: &HashSet<String>,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    if let Expression::CallExpression(ce) = expr {
        if let Expression::Identifier(id) = &ce.callee {
            if setters.contains(id.name.as_str()) {
                let (line, col) = offset_to_line_col(source, ce.span.start);
                issues.push(Issue::new(
                    "setstate-in-render",
                    file,
                    line,
                    col,
                    format!(
                        "{}(...) called directly in component body — infinite re-render. Move to useEffect or handler.",
                        id.name
                    ),
                ));
            }
        }
    }
}
