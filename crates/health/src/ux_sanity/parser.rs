use oxc_allocator::Allocator;
use oxc_ast::ast::Program;
use oxc_parser::Parser;
use oxc_span::SourceType;

pub struct ParsedFile<'a> {
    pub source: &'a str,
    pub program: Program<'a>,
}

pub fn parse<'a>(allocator: &'a Allocator, source: &'a str, path: &str) -> Option<ParsedFile<'a>> {
    let source_type = SourceType::from_path(path).unwrap_or_default();

    let ret = Parser::new(allocator, source, source_type).parse();

    if ret.panicked || !ret.errors.is_empty() {
        return None;
    }

    Some(ParsedFile {
        source,
        program: ret.program,
    })
}

/// Convert span offset to (line, column).
pub fn offset_to_line_col(source: &str, offset: u32) -> (u32, u32) {
    let offset = offset as usize;
    let mut line = 1u32;
    let mut col = 1u32;
    for (i, ch) in source.char_indices() {
        if i >= offset {
            break;
        }
        if ch == '\n' {
            line += 1;
            col = 1;
        } else {
            col += 1;
        }
    }
    (line, col)
}
