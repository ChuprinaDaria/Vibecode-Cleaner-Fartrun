use crate::ux_sanity::issue::Issue;
use crate::ux_sanity::parser::{offset_to_line_col, ParsedFile};
use oxc_ast::ast::*;

/// onClick={async () => { await fetch(...) }} without try/catch.
pub fn check(parsed: &ParsedFile, file: &str) -> Vec<Issue> {
    let mut issues = Vec::new();
    walk_stmts(&parsed.program.body, parsed.source, file, &mut issues);
    issues
}

const EVENT_ATTRS: &[&str] = &[
    "onClick", "onChange", "onSubmit", "onBlur", "onFocus",
    "onMouseEnter", "onMouseLeave", "onKeyDown", "onKeyUp",
];

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
    match expr {
        Expression::JSXElement(jsx) => check_jsx(jsx, source, file, issues),
        Expression::JSXFragment(f) => {
            for c in &f.children {
                if let JSXChild::Element(e) = c {
                    check_jsx(e, source, file, issues);
                }
            }
        }
        Expression::ArrowFunctionExpression(af) => walk_stmts(&af.body.statements, source, file, issues),
        Expression::FunctionExpression(fe) => {
            if let Some(b) = &fe.body {
                walk_stmts(&b.statements, source, file, issues);
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
        let JSXAttributeItem::Attribute(a) = attr else { continue };
        let JSXAttributeName::Identifier(id) = &a.name else { continue };
        if !EVENT_ATTRS.contains(&id.name.as_str()) {
            continue;
        }
        let Some(val) = &a.value else { continue };
        let JSXAttributeValue::ExpressionContainer(ec) = val else { continue };
        let Some(inner) = ec.expression.as_expression() else { continue };

        let (is_async, body_stmts, span) = match inner {
            Expression::ArrowFunctionExpression(af) if af.r#async => {
                (true, Some(&af.body.statements), af.span)
            }
            Expression::FunctionExpression(fe) if fe.r#async => {
                (true, fe.body.as_ref().map(|b| &b.statements), fe.span)
            }
            _ => (false, None, oxc_span::Span::default()),
        };

        if !is_async {
            continue;
        }
        let Some(stmts) = body_stmts else { continue };

        if has_await_without_try(stmts) {
            let (line, col) = offset_to_line_col(source, span.start);
            issues.push(Issue::new(
                "async-handler-no-catch",
                file,
                line,
                col,
                format!(
                    "Async handler {} without try/catch — errors will disappear silently.",
                    id.name
                ),
            ));
        }
    }

    for child in &jsx.children {
        if let JSXChild::Element(e) = child {
            check_jsx(e, source, file, issues);
        }
    }
}

fn has_await_without_try(stmts: &[Statement]) -> bool {
    for s in stmts {
        if let Statement::TryStatement(_) = s {
            continue;
        }
        if stmt_contains_await(s) {
            return true;
        }
    }
    false
}

fn stmt_contains_await(stmt: &Statement) -> bool {
    match stmt {
        Statement::ExpressionStatement(es) => expr_contains_await(&es.expression),
        Statement::VariableDeclaration(vd) => vd.declarations.iter().any(|d| {
            d.init.as_ref().map_or(false, |e| expr_contains_await(e))
        }),
        Statement::ReturnStatement(rs) => {
            rs.argument.as_ref().map_or(false, |e| expr_contains_await(e))
        }
        Statement::IfStatement(is) => {
            stmt_contains_await(&is.consequent)
                || is.alternate.as_ref().map_or(false, |a| stmt_contains_await(a))
        }
        Statement::BlockStatement(bs) => bs.body.iter().any(stmt_contains_await),
        _ => false,
    }
}

fn expr_contains_await(expr: &Expression) -> bool {
    match expr {
        Expression::AwaitExpression(_) => true,
        Expression::CallExpression(ce) => {
            ce.arguments.iter().any(|a| {
                if let Some(e) = a.as_expression() {
                    expr_contains_await(e)
                } else {
                    false
                }
            })
        }
        Expression::ParenthesizedExpression(pe) => expr_contains_await(&pe.expression),
        _ => false,
    }
}
