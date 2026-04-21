use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct Issue {
    pub rule: String,
    pub file: String,
    pub line: u32,
    pub column: u32,
    pub message: String,
    pub severity: String,
}

impl Issue {
    pub fn new(rule: &str, file: &str, line: u32, column: u32, message: String) -> Self {
        Self {
            rule: rule.to_string(),
            file: file.to_string(),
            line,
            column,
            message,
            severity: "warning".to_string(),
        }
    }
}
