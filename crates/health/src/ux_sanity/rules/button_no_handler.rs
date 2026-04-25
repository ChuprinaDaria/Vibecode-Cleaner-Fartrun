use crate::ux_sanity::issue::Issue;
use crate::ux_sanity::parser::{offset_to_line_col, ParsedFile};
use oxc_ast::ast::{Statement, Declaration, ExportDefaultDeclarationKind, Expression, JSXChild, JSXElement, JSXAttributeItem, JSXOpeningElement, JSXElementName, JSXAttributeName, JSXAttributeValue};

/// Finds <button> without onClick, type="submit", onSubmit parent, formAction.
pub fn check(parsed: &ParsedFile, file: &str) -> Vec<Issue> {
    let mut issues = Vec::new();
    walk_statements(&parsed.program.body, false, false, parsed.source, file, &mut issues);
    issues
}

fn walk_statements(
    stmts: &[Statement],
    inside_form: bool,
    inside_clickable: bool,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    for stmt in stmts {
        walk_statement(stmt, inside_form, inside_clickable, source, file, issues);
    }
}

fn walk_statement(
    stmt: &Statement,
    inside_form: bool,
    inside_clickable: bool,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    match stmt {
        Statement::ExpressionStatement(es) => {
            walk_expression(&es.expression, inside_form, inside_clickable, source, file, issues);
        }
        Statement::ReturnStatement(rs) => {
            if let Some(arg) = &rs.argument {
                walk_expression(arg, inside_form, inside_clickable, source, file, issues);
            }
        }
        Statement::FunctionDeclaration(fd) => {
            if let Some(body) = &fd.body {
                walk_statements(&body.statements, inside_form, inside_clickable, source, file, issues);
            }
        }
        Statement::VariableDeclaration(vd) => {
            for decl in &vd.declarations {
                if let Some(init) = &decl.init {
                    walk_expression(init, inside_form, inside_clickable, source, file, issues);
                }
            }
        }
        Statement::IfStatement(is) => {
            walk_statement(&is.consequent, inside_form, inside_clickable, source, file, issues);
            if let Some(alt) = &is.alternate {
                walk_statement(alt, inside_form, inside_clickable, source, file, issues);
            }
        }
        Statement::BlockStatement(bs) => {
            walk_statements(&bs.body, inside_form, inside_clickable, source, file, issues);
        }
        Statement::ExportNamedDeclaration(en) => {
            if let Some(decl) = &en.declaration {
                if let Declaration::FunctionDeclaration(fd) = decl {
                    if let Some(body) = &fd.body {
                        walk_statements(&body.statements, inside_form, inside_clickable, source, file, issues);
                    }
                }
                if let Declaration::VariableDeclaration(vd) = decl {
                    for d in &vd.declarations {
                        if let Some(init) = &d.init {
                            walk_expression(init, inside_form, inside_clickable, source, file, issues);
                        }
                    }
                }
            }
        }
        Statement::ExportDefaultDeclaration(ed) => {
            if let ExportDefaultDeclarationKind::FunctionDeclaration(fd) = &ed.declaration {
                if let Some(body) = &fd.body {
                    walk_statements(&body.statements, inside_form, inside_clickable, source, file, issues);
                }
            }
            if let Some(expr) = ed.declaration.as_expression() {
                walk_expression(expr, inside_form, inside_clickable, source, file, issues);
            }
        }
        _ => {}
    }
}

fn walk_expression(
    expr: &Expression,
    inside_form: bool,
    inside_clickable: bool,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    match expr {
        Expression::JSXElement(jsx) => check_jsx_element(jsx, inside_form, inside_clickable, source, file, issues),
        Expression::JSXFragment(frag) => {
            for child in &frag.children {
                walk_jsx_child(child, inside_form, inside_clickable, source, file, issues);
            }
        }
        Expression::ArrowFunctionExpression(af) => {
            walk_statements(&af.body.statements, inside_form, inside_clickable, source, file, issues);
        }
        Expression::FunctionExpression(fe) => {
            if let Some(body) = &fe.body {
                walk_statements(&body.statements, inside_form, inside_clickable, source, file, issues);
            }
        }
        Expression::ParenthesizedExpression(pe) => {
            walk_expression(&pe.expression, inside_form, inside_clickable, source, file, issues);
        }
        Expression::ConditionalExpression(ce) => {
            walk_expression(&ce.consequent, inside_form, inside_clickable, source, file, issues);
            walk_expression(&ce.alternate, inside_form, inside_clickable, source, file, issues);
        }
        Expression::LogicalExpression(le) => {
            walk_expression(&le.left, inside_form, inside_clickable, source, file, issues);
            walk_expression(&le.right, inside_form, inside_clickable, source, file, issues);
        }
        Expression::CallExpression(ce) => {
            for arg in &ce.arguments {
                if let Some(e) = arg.as_expression() {
                    walk_expression(e, inside_form, inside_clickable, source, file, issues);
                }
            }
        }
        _ => {}
    }
}

fn walk_jsx_child(
    child: &JSXChild,
    inside_form: bool,
    inside_clickable: bool,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    match child {
        JSXChild::Element(el) => check_jsx_element(el, inside_form, inside_clickable, source, file, issues),
        JSXChild::Fragment(frag) => {
            for c in &frag.children {
                walk_jsx_child(c, inside_form, inside_clickable, source, file, issues);
            }
        }
        JSXChild::ExpressionContainer(ec) => {
            if let Some(e) = ec.expression.as_expression() {
                walk_expression(e, inside_form, inside_clickable, source, file, issues);
            }
        }
        _ => {}
    }
}

fn check_jsx_element(
    jsx: &JSXElement,
    inside_form: bool,
    inside_clickable: bool,
    source: &str,
    file: &str,
    issues: &mut Vec<Issue>,
) {
    let tag = jsx_tag_name(&jsx.opening_element);
    let is_form = tag.as_deref() == Some("form");
    let new_inside_form = inside_form || is_form;

    // Track whether this element or any ancestor has onClick (event bubbling)
    let attrs = &jsx.opening_element.attributes;
    let element_has_onclick = attrs.iter().any(|a| is_attr_named(a, "onClick"));
    let new_inside_clickable = inside_clickable || element_has_onclick;

    if tag.as_deref() == Some("button") {
        let has_onclick = element_has_onclick;
        let has_submit_type = attrs.iter().any(|a| is_attr_with_value(a, "type", "submit"));
        let has_form_action = attrs.iter().any(|a| is_attr_named(a, "formAction"));
        let has_on_keydown = attrs.iter().any(|a| is_attr_named(a, "onKeyDown"));
        let has_spread = attrs.iter().any(|a| matches!(a, JSXAttributeItem::SpreadAttribute(_)));

        let is_broken = !has_onclick
            && !has_form_action
            && !has_on_keydown
            && !has_spread
            && !inside_clickable
            && !(inside_form && has_submit_type);

        if is_broken {
            let (line, col) = offset_to_line_col(source, jsx.opening_element.span.start);
            issues.push(Issue::new(
                "button-no-handler",
                file,
                line,
                col,
                "Button without onClick and not type=\"submit\" in a form — does nothing".to_string(),
            ));
        }
    }

    for child in &jsx.children {
        walk_jsx_child(child, new_inside_form, new_inside_clickable, source, file, issues);
    }
}

fn jsx_tag_name(opening: &JSXOpeningElement) -> Option<String> {
    match &opening.name {
        JSXElementName::Identifier(id) => Some(id.name.to_string()),
        _ => None,
    }
}

fn is_attr_named(attr: &JSXAttributeItem, name: &str) -> bool {
    if let JSXAttributeItem::Attribute(a) = attr {
        if let JSXAttributeName::Identifier(id) = &a.name {
            return id.name.as_str() == name;
        }
    }
    false
}

fn is_attr_with_value(attr: &JSXAttributeItem, name: &str, value: &str) -> bool {
    if let JSXAttributeItem::Attribute(a) = attr {
        if let JSXAttributeName::Identifier(id) = &a.name {
            if id.name.as_str() != name {
                return false;
            }
            if let Some(val) = &a.value {
                if let JSXAttributeValue::StringLiteral(sl) = val {
                    return sl.value.as_str() == value;
                }
            }
        }
    }
    false
}
