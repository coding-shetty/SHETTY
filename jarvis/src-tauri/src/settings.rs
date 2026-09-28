use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings { pub ollama_url:String, pub text_model:String, pub vision_model:String, pub temperature:f32, pub context_size:u32, pub wake_word:String, pub global_hotkey:String, pub tts_voice:String, pub speaking_speed:f32, pub confirmation_policy:String, pub memory_enabled:bool }
impl Default for Settings { fn default()->Self{Self{ollama_url:"http://localhost:11434".into(),text_model:"llama3.2".into(),vision_model:"llava".into(),temperature:0.2,context_size:8192,wake_word:"Hey Jarvis".into(),global_hotkey:"CommandOrControl+Shift+J".into(),tts_voice:"Samantha".into(),speaking_speed:1.0,confirmation_policy:"safe".into(),memory_enabled:true}} }
fn path()->PathBuf{dirs::config_local_dir().unwrap_or_else(||PathBuf::from(".")).join("jarvis").join("settings.json")}
#[tauri::command] pub fn settings_get()->Result<Settings,String>{let p=path();if !p.exists(){return Ok(Settings::default())}serde_json::from_str(&fs::read_to_string(p).map_err(|e|e.to_string())?).map_err(|e|e.to_string())}
#[tauri::command] pub fn settings_update(settings:Settings)->Result<Settings,String>{if !(0.0..=2.0).contains(&settings.temperature){return Err("Temperature must be between 0 and 2".into())}if !(0.25..=4.0).contains(&settings.speaking_speed){return Err("Speaking speed must be between 0.25 and 4".into())}let p=path();if let Some(parent)=p.parent(){fs::create_dir_all(parent).map_err(|e|e.to_string())?}fs::write(p,serde_json::to_string_pretty(&settings).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;Ok(settings)}
#[tauri::command] pub fn settings_reset()->Result<Settings,String>{settings_update(Settings::default())}
#[cfg(test)]mod tests{use super::*;#[test]fn defaults_are_local(){assert!(Settings::default().ollama_url.contains("localhost"));assert!(Settings::default().memory_enabled);}}
