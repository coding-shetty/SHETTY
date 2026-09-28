mod settings;
mod memory;
mod agent;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, fs, path::PathBuf, process::Command};
use tauri::State;
use tokio::sync::Mutex;

#[derive(Default)] pub struct AppState { pub history: Mutex<Vec<(String,String)>> }
#[derive(Serialize, Clone)] pub struct Activity { pub id:String, pub label:String, pub detail:Option<String>, pub status:String, pub at:String }
#[derive(Serialize)] pub struct AskResult { pub reply:String, pub activities:Vec<Activity> }
#[derive(Deserialize)] struct OllamaResponse { response:String }

fn activity(label:&str, detail:Option<String>, status:&str) -> Activity { Activity { id:uuid(), label:label.into(), detail, status:status.into(), at:chrono::Local::now().format("%H:%M:%S").to_string() } }
fn uuid()->String { format!("{}-{}", chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default(), std::process::id()) }
fn memory_path()->PathBuf { dirs::data_local_dir().unwrap_or_else(||PathBuf::from("." )).join("jarvis").join("memory.json") }
fn risk(command:&str)->&'static str { let c=command.to_lowercase(); if ["rm -rf","sudo","diskutil","shutdown","reboot","git reset --hard","git push --force","kill "].iter().any(|x|c.contains(x)){"CRITICAL"} else if ["rm ","delete","drop database","chmod","mv "].iter().any(|x|c.contains(x)){"HIGH"} else if ["npm install","pip install","cargo build","git "].iter().any(|x|c.contains(x)){"MEDIUM"} else {"LOW"} }

#[tauri::command]
pub async fn diagnostics() -> BTreeMap<String,String> { let mut out=BTreeMap::new(); let ollama=reqwest::get("http://localhost:11434/api/tags").await.is_ok(); out.insert("Ollama".into(),if ollama{"Connected".into()}else{"Not connected".into()}); out.insert("Terminal".into(),if Command::new("sh").arg("-c").arg("command -v sh").output().map(|x|x.status.success()).unwrap_or(false){"Ready".into()}else{"Unavailable".into()}); out.insert("Memory".into(),if memory_path().exists(){"Stored locally".into()}else{"Ready".into()}); out.insert("Platform".into(),std::env::consts::OS.into()); out.insert("Screen Capture".into(),if cfg!(target_os="macos"){"Requires macOS permission".into()}else{"macOS build required".into()}); out }

#[tauri::command]
pub async fn agent_ask(text:String, state:State<'_,AppState>) -> Result<AskResult,String> { let mut acts=vec![activity("Understanding request",Some(text.clone()),"active")]; let lower=text.to_lowercase(); if lower.contains("open safari") { return open_app_inner("Safari".into()).map(|reply| AskResult{reply,activities:vec![activity("Opening Safari",Some("Native macOS open command".into()),"done")]}); }
 if lower.contains("node version") { let out=Command::new("node").arg("--version").output().map_err(|e|e.to_string())?; let value=String::from_utf8_lossy(&out.stdout).trim().to_string(); let reply=if out.status.success(){format!("Node is {}.",value)}else{"I couldn't read the Node version.".into()}; acts.push(activity("Running terminal command",Some("node --version".into()),"done")); return Ok(AskResult{reply,activities:acts}); }
 if lower.contains("remember") { remember_inner(text.clone())?; return Ok(AskResult{reply:"I’ll remember that locally.".into(),activities:vec![activity("Saving local memory",None,"done")]}); }
 acts.push(activity("Consulting Ollama",Some("Local model only; screen data is not uploaded".into()),"active")); let registry=agent::default_registry(); let body=serde_json::json!({"model":"llama3.2","prompt":format!("You are JARVIS, concise, calm, helpful, mildly witty. You may only request registered tools. Never claim success without verified tool results. Registered tools:\n{}\nUser: {}",agent::tools_prompt(&registry),text),"stream":false}); let response=reqwest::Client::new().post("http://localhost:11434/api/generate").json(&body).send().await.map_err(|_|"I can't connect to Ollama. Please start Ollama and try again.".to_string())?; if !response.status().is_success(){return Err("I can't connect to Ollama. Please start Ollama and try again.".into())} let data:OllamaResponse=response.json().await.map_err(|e|e.to_string())?; state.history.lock().await.push((text,data.response.clone())); acts.push(activity("Response received",None,"done")); Ok(AskResult{reply:data.response,activities:acts}) }

fn open_app_inner(name:String)->Result<String,String>{ if !cfg!(target_os="macos"){return Err("Native application control is available in the macOS build; this environment is not macOS.".into())} let status=Command::new("open").args(["-a",&name]).status().map_err(|e|e.to_string())?; if status.success(){Ok(format!("Opening {}.",name))}else{Err(format!("macOS rejected the request to open {}.",name))} }
#[tauri::command] pub async fn open_app(name:String)->Result<String,String>{open_app_inner(name)}
#[tauri::command] pub async fn remember(text:String)->Result<String,String>{remember_inner(text)}
fn remember_inner(text:String)->Result<String,String>{let path=memory_path();if let Some(parent)=path.parent(){fs::create_dir_all(parent).map_err(|e|e.to_string())?}let mut values:Vec<String>=if path.exists(){serde_json::from_str(&fs::read_to_string(&path).map_err(|e|e.to_string())?).unwrap_or_default()}else{Vec::new()};values.push(text);fs::write(path,serde_json::to_string_pretty(&values).unwrap()).map_err(|e|e.to_string())?;Ok("Saved".into())}
#[tauri::command] pub fn classify_command(command:String)->String{risk(&command).into()}
#[tauri::command] pub fn run_safe_command(command:String, confirmed:bool)->Result<String,String>{let level=risk(&command);if level!="LOW"&&!confirmed{return Err(format!("Confirmation required for {} risk command.",level))}let out=Command::new("sh").args(["-lc",&command]).output().map_err(|e|e.to_string())?;Ok(serde_json::json!({"success":out.status.success(),"risk":level,"stdout":String::from_utf8_lossy(&out.stdout),"stderr":String::from_utf8_lossy(&out.stderr)}).to_string())}

#[cfg_attr(mobile, tauri::mobile_entry_point)] pub fn run(){tauri::Builder::default().manage(AppState::default()).invoke_handler(tauri::generate_handler![diagnostics,agent_ask,open_app,remember,classify_command,run_safe_command,list_tools,memory::memory_store,memory::memory_search,memory::memory_get,memory::memory_delete,memory::memory_clear,settings::settings_get,settings::settings_update,settings::settings_reset]).run(tauri::generate_context!()).expect("error while running JARVIS");}

#[cfg(test)] mod tests { use super::risk; #[test] fn risk_policy(){ assert_eq!(risk("pwd"),"LOW"); assert_eq!(risk("git status"),"MEDIUM"); assert_eq!(risk("rm ./cache"),"HIGH"); assert_eq!(risk("rm -rf ./cache"),"CRITICAL"); assert_eq!(risk("sudo shutdown -h now"),"CRITICAL"); } }

#[tauri::command]
pub fn list_tools()->Vec<agent::ToolDefinition>{agent::default_registry().definitions()}
