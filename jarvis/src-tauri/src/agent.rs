use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum RiskLevel { Low, Medium, High, Critical }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolDefinition { pub name:String, pub description:String, pub input_schema:serde_json::Value, pub risk:RiskLevel, pub requires_confirmation:bool }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall { pub name:String, pub arguments:serde_json::Value }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult { pub success:bool, pub tool:String, pub output:serde_json::Value, pub verified:bool }
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AgentContext { pub user_request:String, pub conversation:Vec<(String,String)>, pub active_app:Option<String>, pub active_window:Option<String>, pub screen_context:Option<String>, pub relevant_memory:Vec<String> }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentPlan { pub steps:Vec<ToolCall>, pub final_response:Option<String> }

#[derive(Default)] pub struct ToolRegistry { tools:BTreeMap<String,ToolDefinition> }
impl ToolRegistry {
  pub fn register(&mut self, tool:ToolDefinition){ self.tools.insert(tool.name.clone(),tool); }
  pub fn get(&self,name:&str)->Option<&ToolDefinition>{self.tools.get(name)}
  pub fn definitions(&self)->Vec<ToolDefinition>{self.tools.values().cloned().collect()}
  pub fn validate(&self, call:&ToolCall)->Result<&ToolDefinition,String>{self.get(&call.name).ok_or_else(||format!("Tool '{}' is not registered",call.name))}
}
fn schema(properties:serde_json::Value)->serde_json::Value{serde_json::json!({"type":"object","properties":properties})}
pub fn default_registry()->ToolRegistry { let mut r=ToolRegistry::default();
  r.register(ToolDefinition{name:"application.open".into(),description:"Open a named macOS application and verify the launch.".into(),input_schema:schema(serde_json::json!({"name":{"type":"string"}})),risk:RiskLevel::Low,requires_confirmation:false});
  r.register(ToolDefinition{name:"terminal.run".into(),description:"Run a validated terminal command and return stdout/stderr.".into(),input_schema:schema(serde_json::json!({"command":{"type":"string"},"confirmed":{"type":"boolean"}})),risk:RiskLevel::Medium,requires_confirmation:true});
  r.register(ToolDefinition{name:"screen.capture".into(),description:"Capture the primary display after Screen Recording permission is granted.".into(),input_schema:schema(serde_json::json!({})),risk:RiskLevel::Low,requires_confirmation:false});
  r.register(ToolDefinition{name:"memory.store".into(),description:"Store explicitly requested local memory.".into(),input_schema:schema(serde_json::json!({"content":{"type":"string"}})),risk:RiskLevel::Low,requires_confirmation:false});
  r
}
pub fn tools_prompt(r:&ToolRegistry)->String{r.definitions().into_iter().map(|t|format!("{}: {}",t.name,t.description)).collect::<Vec<_>>().join("\n")}
#[cfg(test)] mod tests { use super::*; #[test] fn registry_validates_only_registered_tools(){let r=default_registry();assert!(r.get("application.open").is_some());assert!(r.validate(&ToolCall{name:"not.real".into(),arguments:serde_json::json!({})}).is_err());} }
