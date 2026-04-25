use crate::ux_sanity::issue::Issue;
use crate::ux_sanity::parser::{offset_to_line_col, ParsedFile};
use oxc_ast::ast::{Statement, Declaration, ExportDefaultDeclarationKind, Expression};

/// useEffect(() => {...}) without second argument — re-runs on every render.
pub fn check(parsed: &ParsedFile, file: &str) -> Vec<Issue> {
    let mut issues = Vec::new();
    walk_stmts(&parsed.program.body, parsed.source, file, &mut issues);
    issues
}

fn walk_stmts(stmts: &[Statement], source: &str, file: &str, issues: &mut Vec<Issue>) {
    for s in stmts {
        walk_stmt(s, source, file, issues);
    }
}

fn walk_stmt(stmt: &Statement, source: &str, file: &str, issues: &mut Vec<Issue>) {
    match stmt {
        Statement::ExpressionStatement(es) => walk_expr(&es.expression, source, file, issues),
        Statement::ReturnStatement(rs) => {
            if let Some(a) = &rs.argument {
                walk_expr(a, source, file, issues);
            }
        }
        Statement::VariableDeclaration(vd) => {
            for d in &vd.declarations {
                if let Some(init) = &d.init {
                    walk_expr(init, source, file, issues);
                }
            }
        }
        Statement::FunctionDeclaration(fd) => {
            if let Some(b) = &fd.body {
                walk_stmts(&b.statements, source, file, issues);
            }
        }
        Statement::BlockStatement(bs) => walk_stmts(&bs.body, source, file, issues),
        Statement::IfStatement(is) => {
            walk_stmt(&is.consequent, source, file, issues);
            if let Some(a) = &is.alternate {
                walk_stmt(a, source, file, issues);
            }
        }
        Statement::ExportNamedDeclaration(en) => {
            if let Some(decl) = &en.declaration {
                if let Declaration::FunctionDeclaration(fd) = decl {
                    if let Some(body) = &fd.body {
                        walk_stmts(&body.statements, source, file, issues);
                    }
                }
                if let Declaration::VariableDeclaration(vd) = decl {
                    for d in &vd.declarations {
                        if let Some(init) = &d.init {
                            walk_expr(init, source, file, issues);
                        }
                    }
                }
            }
        }
        Statement::ExportDefaultDeclaration(ed) => {
            if let ExportDefaultDeclarationKind::FunctionDeclaration(fd) = &ed.declaration {
                if let Some(body) = &fd.body {
                    walk_stmts(&body.statements, source, file, issues);
                }
            }
            if let Some(expr) = ed.declaration.as_expression() {
                walk_expr(expr, source, file, issues);
            }
        }
        _ => {}
    }
}

fn walk_expr(expr: &Expression, source: &str, file: &str, issues: &mut Vec<Issue>) {
    if let Expression::CallExpression(ce) = expr {
        if is_use_effect(&ce.callee) && ce.arguments.len() == 1 {
            let (line, col) = offset_to_line_col(source, ce.span.start);
            issues.push(Issue::new(
                "effect-missing-deps-array",
                file,
                line,
                col,
                "useEffect without dependency array — runs on every render. Add [] or dependencies.".to_string(),
            ));
        }
    }

    match expr {
        Expression::ArrowFunctionExpression(af) => walk_stmts(&af.body.statements, source, file, issues),
        Expression::FunctionExpression(fe) => {
            if let Some(b) = &fe.body {
                walk_stmts(&b.statements, source, file, issues);
            }
        }
        Expression::CallExpression(ce) => {
            for arg in &ce.arguments {
                if let Some(e) = arg.as_expression() {
                    walk_expr(e, source, file, issues);
                }
            }
        }
        _ => {}
    }
}

fn is_use_effect(callee: &Expression) -> bool {
    match callee {
        Expression::Identifier(id) => {
            let n = id.name.as_str();
            n == "useEffect" || n == "useLayoutEffect"
        }
        Expression::StaticMemberExpression(sme) => {
            let prop = sme.property.name.as_str();
            prop == "useEffect" || prop == "useLayoutEffect"
        }
        _ => false,
    }
}
