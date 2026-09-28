import { invoke } from '@tauri-apps/api/core';

export type JarvisState = 'IDLE'|'LISTENING'|'THINKING'|'ACTING'|'SPEAKING'|'CONFIRMATION'|'ERROR';
export type Activity = { id:string; label:string; detail?:string; status:'done'|'active'|'waiting'|'error'; at:string };
const tauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
export async function call<T>(cmd:string, args?:Record<string,unknown>): Promise<T> {
  if (!tauri) throw new Error('JARVIS native commands are available in the macOS desktop build.');
  return invoke<T>(cmd, args);
}
export async function health() { return call<Record<string, string>>('diagnostics'); }
export async function ask(text:string) { return call<{reply:string; activities:Activity[]}>('agent_ask', { text }); }
export async function remember(text:string) { return call<string>('remember', { text }); }
export async function openApp(name:string) { return call<string>('open_app', { name }); }
