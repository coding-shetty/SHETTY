use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord { pub id:String, #[serde(rename="type")] pub kind:String, pub content:String, pub created_at:String, pub updated_at:String }
fn path()->PathBuf { dirs::data_local_dir().unwrap_or_else(||PathBuf::from(".")).join("jarvis").join("memories.json") }
fn load()->Result<Vec<MemoryRecord>,String>{let p=path();if !p.exists(){return Ok(Vec::new())}serde_json::from_str(&fs::read_to_string(p).map_err(|e|e.to_string())?).map_err(|e|e.to_string())}
fn save(items:&[MemoryRecord])->Result<(),String>{let p=path();if let Some(parent)=p.parent(){fs::create_dir_all(parent).map_err(|e|e.to_string())?}fs::write(p,serde_json::to_string_pretty(items).map_err(|e|e.to_string())?).map_err(|e|e.to_string())}
fn id()->String{format!("mem-{}",chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default())}
#[tauri::command] pub fn memory_store(kind:String,content:String)->Result<MemoryRecord,String>{if content.trim().is_empty(){return Err("Memory content cannot be empty".into())}let now=chrono::Utc::now().to_rfc3339();let item=MemoryRecord{id:id(),kind,content,created_at:now.clone(),updated_at:now};let mut all=load()?;all.push(item.clone());save(&all)?;Ok(item)}
#[tauri::command] pub fn memory_search(query:String)->Result<Vec<MemoryRecord>,String>{let q=query.to_lowercase();Ok(load()?.into_iter().filter(|m|m.content.to_lowercase().contains(&q)||m.kind.to_lowercase().contains(&q)).collect())}
#[tauri::command] pub fn memory_get(id:String)->Result<Option<MemoryRecord>,String>{Ok(load()?.into_iter().find(|m|m.id==id))}
#[tauri::command] pub fn memory_delete(id:String)->Result<bool,String>{let all=load()?;let next:Vec<_>=all.iter().filter(|m|m.id!=id).cloned().collect();let changed=next.len()!=all.len();if changed{save(&next)?}Ok(changed)}
#[tauri::command] pub fn memory_clear()->Result<(),String>{let p=path();if p.exists(){fs::remove_file(p).map_err(|e|e.to_string())?}Ok(())}
#[cfg(test)] mod tests{use super::*;#[test]fn ids_are_prefixed(){assert!(id().starts_with("mem-"));}}
