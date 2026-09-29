import { describe, expect, it } from 'vitest';
import { classifyCommand } from '../src/risk';
describe('command risk policy',()=>{it('allows harmless reads',()=>expect(classifyCommand('node --version')).toBe('LOW'));it('gates repository mutations',()=>expect(classifyCommand('git status')).toBe('MEDIUM'));it('flags deletion',()=>expect(classifyCommand('rm ./cache')).toBe('HIGH'));it('blocks destructive commands',()=>expect(classifyCommand('rm -rf ./cache')).toBe('CRITICAL'));});
