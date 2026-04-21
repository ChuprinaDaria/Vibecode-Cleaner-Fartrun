//! sentinel — cross-platform host IDS for dev environments.

mod processes;
mod network;
mod filesystem;
mod crontab;
mod secrets;
mod autostart;
mod container_escape;
mod supply_chain;
mod git_hooks;
mod env_leak;

use pyo3::prelude::*;

#[pymodule]
fn sentinel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Original scanners
    m.add_class::<processes::ProcessFinding>()?;
    m.add_function(wrap_pyfunction!(processes::scan_processes, m)?)?;
    m.add_class::<network::NetworkFinding>()?;
    m.add_function(wrap_pyfunction!(network::scan_network, m)?)?;
    m.add_class::<filesystem::FileFinding>()?;
    m.add_function(wrap_pyfunction!(filesystem::scan_filesystem, m)?)?;
    m.add_class::<crontab::CronFinding>()?;
    m.add_function(wrap_pyfunction!(crontab::scan_scheduled_tasks, m)?)?;
    m.add_class::<secrets::SecretFinding>()?;
    m.add_function(wrap_pyfunction!(secrets::scan_secrets, m)?)?;
    m.add_class::<autostart::AutostartFinding>()?;
    m.add_function(wrap_pyfunction!(autostart::scan_autostart, m)?)?;

    // New scanners (Phase 4)
    m.add_class::<container_escape::ContainerEscapeFinding>()?;
    m.add_function(wrap_pyfunction!(container_escape::scan_container_escape, m)?)?;
    m.add_class::<supply_chain::SupplyChainFinding>()?;
    m.add_function(wrap_pyfunction!(supply_chain::scan_supply_chain, m)?)?;
    m.add_class::<git_hooks::GitHookFinding>()?;
    m.add_function(wrap_pyfunction!(git_hooks::scan_git_hooks, m)?)?;
    m.add_class::<env_leak::EnvLeakFinding>()?;
    m.add_function(wrap_pyfunction!(env_leak::scan_env_leaks, m)?)?;

    Ok(())
}
