//! health — project health scanner for vibe coders.

mod common;
mod dead_code;
mod duplicates;
mod entry_points;
mod file_tree;
mod module_map;
mod monsters;
mod overengineering;
mod reusable;
mod scan_ctx;
mod tech_debt;
mod ux_sanity;

use pyo3::prelude::*;

#[pymodule]
fn health(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<scan_ctx::ScanContext>()?;

    m.add_class::<file_tree::FileTreeResult>()?;
    m.add_function(wrap_pyfunction!(file_tree::scan_file_tree, m)?)?;

    m.add_class::<entry_points::EntryPoint>()?;
    m.add_class::<entry_points::EntryPointsResult>()?;
    m.add_function(wrap_pyfunction!(entry_points::scan_entry_points, m)?)?;

    m.add_class::<monsters::MonsterFile>()?;
    m.add_class::<monsters::MonstersResult>()?;
    m.add_function(wrap_pyfunction!(monsters::scan_monsters, m)?)?;
    m.add_function(wrap_pyfunction!(monsters::scan_monsters_files, m)?)?;
    m.add_function(wrap_pyfunction!(monsters::scan_monsters_with_context, m)?)?;

    m.add_class::<module_map::ModuleInfo>()?;
    m.add_class::<module_map::CircularDep>()?;
    m.add_class::<module_map::ModuleMapResult>()?;
    m.add_function(wrap_pyfunction!(module_map::scan_module_map, m)?)?;
    m.add_function(wrap_pyfunction!(module_map::scan_module_map_with_context, m)?)?;

    m.add_class::<dead_code::UnusedImport>()?;
    m.add_class::<dead_code::UnusedDefinition>()?;
    m.add_class::<dead_code::CommentedBlock>()?;
    m.add_class::<dead_code::DeadCodeResult>()?;
    m.add_function(wrap_pyfunction!(dead_code::scan_dead_code, m)?)?;
    m.add_function(wrap_pyfunction!(dead_code::scan_dead_code_with_context, m)?)?;

    m.add_class::<tech_debt::MissingType>()?;
    m.add_class::<tech_debt::ErrorGap>()?;
    m.add_class::<tech_debt::HardcodedValue>()?;
    m.add_class::<tech_debt::TodoItem>()?;
    m.add_class::<tech_debt::TechDebtResult>()?;
    m.add_function(wrap_pyfunction!(tech_debt::scan_tech_debt, m)?)?;
    m.add_function(wrap_pyfunction!(tech_debt::scan_tech_debt_files, m)?)?;
    m.add_function(wrap_pyfunction!(tech_debt::scan_tech_debt_with_context, m)?)?;

    m.add_class::<duplicates::DuplicateBlock>()?;
    m.add_class::<duplicates::DuplicatesResult>()?;
    m.add_function(wrap_pyfunction!(duplicates::scan_duplicates, m)?)?;

    m.add_class::<overengineering::OverengineeringIssue>()?;
    m.add_class::<overengineering::OverengineeringResult>()?;
    m.add_function(wrap_pyfunction!(overengineering::scan_overengineering, m)?)?;
    m.add_function(wrap_pyfunction!(overengineering::scan_overengineering_with_context, m)?)?;

    m.add_class::<reusable::ReusablePattern>()?;
    m.add_class::<reusable::ReusableResult>()?;
    m.add_function(wrap_pyfunction!(reusable::scan_reusable, m)?)?;

    m.add_function(wrap_pyfunction!(scan_ux_sanity, m)?)?;

    Ok(())
}

#[pyfunction]
fn scan_ux_sanity(path: String) -> PyResult<String> {
    let issues = ux_sanity::scan_directory(std::path::Path::new(&path));
    serde_json::to_string(&issues)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}
