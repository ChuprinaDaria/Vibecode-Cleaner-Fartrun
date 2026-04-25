use crate::ux_sanity::issue::Issue;
use crate::ux_sanity::parser::{offset_to_line_col, ParsedFile};
use oxc_ast::ast::{Statement, Declaration, ExportDefaultDeclarationKind, Expression, JSXChild, JSXElement, JSXAttributeItem, JSXAttributeName, JSXAttributeValue};

/// `onClick={handleClick()`} instead of onClick={handleClick}
/// Triggers only on `CallExpression` with Identifier callee and 0 args.
pub fn check(parsed: &ParsedFile, file: &str) -> Vec<Issue> {
    let mut issues = Vec::new();
    walk(&parsed.program.body, parsed.source, file, &mut issues);
    issues
}

const EVENT_ATTRS: &[&str] = &[
    "onClick", "onChange", "onSubmit", "onBlur", "onFocus",
    "onMouseEnter", "onMouseLeave", "onKeyDown", "onKeyUp",
];

fn walk(stmts: &[Statement], source: &str, file: &str, issues: &mut Vec<Issue>) {
    for stmt in stmts {
        walk_stmt(stmt, source, file, issues);
    }
}

fn walk_stmt(stmt: &Statement, source: &str, file: &str, issues: &mut Vec<Issue>) {
    match stmt {
        Statement::ExpressionStatement(es) => walk_expr(&es.expression, source, file, issues),
        Statement::ReturnStatement(rs) => {
            if let Some(arg) = &rs.argument {
                walk_expr(arg, source, file, issues);
            }
        }
        Statement::FunctionDeclaration(fd) => {
            if let Some(body) = &fd.body {
                walk(&body.statements, source, file, issues);
            }
        }
        Statement::VariableDeclaration(vd) => {
            for d in &vd.declarations {
                if let Some(init) = &d.init {
                    walk_expr(init, source, file, issues);
                }
            }
        }
        Statement::BlockStatement(bs) => walk(&bs.body, source, file, issues),
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
                        walk(&body.statements, source, file, issues);
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
                    walk(&body.statements, source, file, issues);
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
    match expr {
        Expression::JSXElement(jsx) => check_jsx(jsx, source, file, issues),
        Expression::JSXFragment(f) => {
            for c in &f.children {
                if let JSXChild::Element(e) = c {
                    check_jsx(e, source, file, issues);
                }
            }
        }
        Expression::ArrowFunctionExpression(af) => walk(&af.body.statements, source, file, issues),
        Expression::FunctionExpression(fe) => {
            if let Some(b) = &fe.body {
                walk(&b.statements, source, file, issues);
            }
        }
        Expression::ParenthesizedExpression(pe) => walk_expr(&pe.expression, source, file, issues),
        Expression::ConditionalExpression(ce) => {
            walk_expr(&ce.consequent, source, file, issues);
            walk_expr(&ce.alternate, source, file, issues);
        }
        Expression::LogicalExpression(le) => {
            walk_expr(&le.left, source, file, issues);
            walk_expr(&le.right, source, file, issues);
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

fn check_jsx(jsx: &JSXElement, source: &str, file: &str, issues: &mut Vec<Issue>) {
    for attr in &jsx.opening_element.attributes {
        if let JSXAttributeItem::Attribute(a) = attr {
            let attr_name = if let JSXAttributeName::Identifier(id) = &a.name {
                id.name.as_str()
            } else {
                continue;
            };

            if !EVENT_ATTRS.contains(&attr_name) {
                continue;
            }

            let Some(val) = &a.value else { continue };
            let JSXAttributeValue::ExpressionContainer(ec) = val else { continue };
            let Some(inner) = ec.expression.as_expression() else { continue };

            if let Expression::CallExpression(ce) = inner {
                let is_identifier_callee = matches!(&ce.callee, Expression::Identifier(_));
                let no_args = ce.arguments.is_empty();

                if is_identifier_callee && no_args {
                    let (line, col) = offset_to_line_col(source, ce.span.start);
                    issues.push(Issue::new(
                        "handler-called-not-referenced",
                        file,
                        line,
                        col,
                        format!(
                            "{attr_name}={{handler()}} calls function at render time. Use {attr_name}={{handler}} instead"
                        ),
                    ));
                }
            }
        }
    }

    for child in &jsx.children {
        if let JSXChild::Element(e) = child {
            check_jsx(e, source, file, issues);
        } else if let JSXChild::ExpressionContainer(ec) = child {
            if let Some(e) = ec.expression.as_expression() {
                walk_expr(e, source, file, issues);
            }
        }
    }
}
