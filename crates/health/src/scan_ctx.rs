//! Cross-scanner cache for file contents and tree-sitter ASTs.
//!
//! Each scanner used to read every source file from disk and re-parse
//! every Python/JS file independently. Within one `run_all_checks` call,
//! a typical Python file got parsed by both `dead_code` and `module_map`
//! — the same bytes, the same parser, twice.
//!
//! `ScanContext` is a per-run cache. The orchestrator constructs one,
//! passes it to scanner pyfunctions that opted into the `_with_context`
//! variants, and lets it drop at the end. File contents and parsed
//! trees are stored as `Arc` so multiple scanners can share the same
//! allocation without copying.

use std::cell::RefCell;
use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;

use pyo3::prelude::*;
use tree_sitter::{Parser, Tree};

/// Languages we cache trees for. The integer discriminant is what we
/// use as the cache key (tree-sitter `Language` is not `Hash`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CtxLang {
    Python,
    JavaScript,
    TypeScript,
    Tsx,
}

impl CtxLang {
    pub(crate) fn ts_language(self) -> tree_sitter::Language {
        match self {
            CtxLang::Python => tree_sitter_python::LANGUAGE.into(),
            CtxLang::JavaScript => tree_sitter_javascript::LANGUAGE.into(),
            CtxLang::TypeScript => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
            CtxLang::Tsx => tree_sitter_typescript::LANGUAGE_TSX.into(),
        }
    }

    /// Map a file extension (lowercased, no dot) to a cacheable language.
    /// Returns `None` for languages we don't tree-sitter-parse here.
    pub fn from_ext(ext: &str) -> Option<Self> {
        match ext {
            "py" => Some(CtxLang::Python),
            "js" | "mjs" | "cjs" | "jsx" => Some(CtxLang::JavaScript),
            "ts" | "mts" | "cts" => Some(CtxLang::TypeScript),
            "tsx" => Some(CtxLang::Tsx),
            _ => None,
        }
    }
}

struct ScanCtxInner {
    file_cache: HashMap<String, Arc<String>>,
    tree_cache: HashMap<(String, CtxLang), Arc<Tree>>,
    file_hits: u64,
    file_misses: u64,
    tree_hits: u64,
    tree_misses: u64,
}

/// Per-run cache. `RefCell` because PyO3 hands us `&ScanContext` (the
/// orchestrator owns the Python object) and scanner code mutates the
/// inner caches as it loads files and parses trees.
///
/// Marked `unsendable` so PyO3 enforces single-thread access — the GIL
/// already serialises scanner calls on CPython, so this matches reality
/// and lets us avoid wrapping the cache in a `Mutex`.
#[pyclass(unsendable)]
pub struct ScanContext {
    inner: RefCell<ScanCtxInner>,
}

impl ScanContext {
    /// Read a file once per run. The returned `Arc<String>` is shared
    /// between every scanner that asks for the same `rel_path`.
    pub fn read_file(&self, rel_path: &str, abs_path: &Path) -> Option<Arc<String>> {
        {
            let mut inner = self.inner.borrow_mut();
            if let Some(s) = inner.file_cache.get(rel_path).cloned() {
                inner.file_hits += 1;
                return Some(s);
            }
            inner.file_misses += 1;
        }
        let content = std::fs::read_to_string(abs_path).ok()?;
        let arc = Arc::new(content);
        self.inner
            .borrow_mut()
            .file_cache
            .insert(rel_path.to_string(), Arc::clone(&arc));
        Some(arc)
    }

    /// Get an `Arc<Tree>` for `rel_path` parsed as `lang`. Parses on
    /// first call; subsequent calls return the same Arc (free clone).
    /// Returns `None` only when `set_language` or `parse` itself fails.
    pub fn parse(&self, rel_path: &str, lang: CtxLang, content: &str) -> Option<Arc<Tree>> {
        let key = (rel_path.to_string(), lang);
        {
            let mut inner = self.inner.borrow_mut();
            if let Some(t) = inner.tree_cache.get(&key).cloned() {
                inner.tree_hits += 1;
                return Some(t);
            }
            inner.tree_misses += 1;
        }
        let mut parser = Parser::new();
        if let Err(e) = parser.set_language(&lang.ts_language()) {
            eprintln!("scan_ctx: set_language({lang:?}) failed for {rel_path}: {e}");
            return None;
        }
        let tree = parser.parse(content, None)?;
        let arc = Arc::new(tree);
        self.inner
            .borrow_mut()
            .tree_cache
            .insert(key, Arc::clone(&arc));
        Some(arc)
    }
}

/// Get an `Arc<Tree>` for `(rel_path, lang)` using `ctx` when provided,
/// otherwise parsing in place. Shared by every scanner that opts into
/// the context cache so they all hit the same `set_language` /
/// fallback / logging path.
pub fn parse_or_cached(
    ctx: Option<&ScanContext>,
    rel_path: &str,
    lang: CtxLang,
    content: &str,
) -> Option<Arc<Tree>> {
    if let Some(c) = ctx {
        return c.parse(rel_path, lang, content);
    }
    let mut parser = Parser::new();
    if let Err(e) = parser.set_language(&lang.ts_language()) {
        eprintln!("scan_ctx::parse_or_cached: set_language({lang:?}) failed for {rel_path}: {e}");
        return None;
    }
    parser.parse(content, None).map(Arc::new)
}

#[pymethods]
impl ScanContext {
    #[new]
    fn py_new() -> Self {
        Self {
            inner: RefCell::new(ScanCtxInner {
                file_cache: HashMap::new(),
                tree_cache: HashMap::new(),
                file_hits: 0,
                file_misses: 0,
                tree_hits: 0,
                tree_misses: 0,
            }),
        }
    }

    /// `(file_hits, file_misses, tree_hits, tree_misses)` — exposed for
    /// tests and debugging so callers can verify the cache is doing work.
    fn stats(&self) -> (u64, u64, u64, u64) {
        let inner = self.inner.borrow();
        (inner.file_hits, inner.file_misses, inner.tree_hits, inner.tree_misses)
    }

    /// Number of (file_cache, tree_cache) entries.
    fn cache_size(&self) -> (usize, usize) {
        let inner = self.inner.borrow();
        (inner.file_cache.len(), inner.tree_cache.len())
    }
}
