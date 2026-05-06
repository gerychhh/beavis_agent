import React, { useEffect, useMemo, useRef, useState } from 'react'

// === INJECTED GLOBAL STYLES (Обновлено с новыми эффектами) ===
const GlobalStyles = () => (
  <style>{`
    html, body, #root {
      width: 100%; min-width: 100%; min-height: 100%; margin: 0; padding: 0;
      background: #050505; overflow: hidden;
    }
    * { box-sizing: border-box; }
    body { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    button, input, textarea, select { font: inherit; }
    button { padding: 0; border: 0; background: transparent; color: inherit; cursor: pointer; }
    
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type="number"] { appearance: textfield; -moz-appearance: textfield; }

    .custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); border-radius: 999px; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 999px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.3); }

    .slang-chip .chip-remove { opacity: 0; }
    .slang-chip:hover .chip-remove { opacity: 1; }

    @keyframes fadeSlideUp {
      from { opacity: 0; transform: translateY(15px) scale(0.98); filter: blur(4px); }
      to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0px); }
    }
    .page-enter { animation: fadeSlideUp 500ms cubic-bezier(0.16, 1, 0.3, 1) both; }

    /* Staggered entries for lists */
    .stagger-1 { animation-delay: 50ms; }
    .stagger-2 { animation-delay: 100ms; }
    .stagger-3 { animation-delay: 150ms; }
    .stagger-4 { animation-delay: 200ms; }
    .stagger-5 { animation-delay: 250ms; }

    @keyframes toastIn {
      from { opacity: 0; transform: translateX(20px) scale(0.9); }
      to { opacity: 1; transform: translateX(0) scale(1); }
    }
    .toast-in { animation: toastIn 300ms cubic-bezier(0.16, 1, 0.3, 1) both; }

    input, textarea, select { color-scheme: dark; background-color: transparent; color: #fff; }
    input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus {
      -webkit-text-fill-color: #fff; box-shadow: 0 0 0 1000px rgba(9,9,11,.95) inset; transition: background-color 9999s ease-out;
    }
    select option { background: #09090b; color: #fff; }

    @keyframes dropdownIn {
      from { opacity: 0; transform: translateY(-4px) scale(0.97); filter: blur(2px); }
      to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0px); }
    }
    .dropdown-in { animation: dropdownIn 150ms cubic-bezier(0.16, 1, 0.3, 1) both; }

    .glass-dropdown-trigger {
      border: 1px solid rgba(255, 255, 255, 0.1); background: rgba(9, 9, 11, 0.6); box-shadow: inset 0 1px 1px rgba(255,255,255,0.05);
    }
    .glass-dropdown-trigger:hover { border-color: rgba(255, 255, 255, 0.2); background: rgba(24, 24, 27, 0.8); }
    .glass-dropdown-trigger:focus-visible { outline: none; border-color: rgba(255, 255, 255, 0.4); background: rgba(24, 24, 27, 0.9); }

    /* Audio Wave */
    @keyframes audioWave { 0%, 100% { height: 8px; } 50% { height: 28px; } }
    .audio-bar { width: 4px; border-radius: 4px; background: #000; animation: audioWave 1.2s ease-in-out infinite; }

    /* Shine effect for buttons */
    @keyframes shine {
      0% { transform: translateX(-150%) skewX(-20deg); }
      15%, 100% { transform: translateX(200%) skewX(-20deg); }
    }
    .btn-shine {
      position: relative; overflow: hidden;
    }
    .btn-shine::after {
      content: ''; position: absolute; top: 0; left: 0; width: 40%; height: 100%;
      background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0) 100%);
      transform: translateX(-150%) skewX(-20deg);
      animation: shine 4s infinite cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Typewriter cursor blinking */
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
    .cursor-blink { animation: blink 1s step-end infinite; }
  `}</style>
)

const THEME = {
  app: 'relative flex min-h-screen flex-col overflow-hidden bg-[#050505] text-white selection:bg-white/30 selection:text-black',
  header: 'relative z-20 hidden md:flex h-[68px] w-full items-center justify-between border-b border-white/10 bg-black/30 px-6 shadow-[0_4px_30px_rgba(0,0,0,.22)] backdrop-blur-[50px]',
  mobileHeader: 'relative z-20 flex md:hidden h-[60px] w-full items-center justify-between border-b border-white/10 bg-black/40 px-4 backdrop-blur-xl',
  page: 'mx-auto max-w-7xl px-4 md:px-6 py-6 md:py-8 page-enter',
  pageNarrow: 'mx-auto max-w-5xl px-4 md:px-6 py-6 md:py-8 page-enter',
  surface: 'rounded-[24px] md:rounded-[28px] border border-white/[0.08] bg-[#0c0c0e]/80 shadow-[0_20px_70px_rgba(0,0,0,.4),inset_0_1px_1px_rgba(255,255,255,.05)] backdrop-blur-[46px] transition-all duration-400 ease-out',
  surfaceHover: 'hover:-translate-y-1.5 hover:border-white/20 hover:bg-[#121215]/90 hover:shadow-[0_30px_90px_rgba(0,0,0,.6),inset_0_1px_1px_rgba(255,255,255,.1)]',
  input: 'w-full rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 text-sm text-white outline-none transition-all duration-300 placeholder:text-white/20 focus:border-white/40 focus:bg-white/[0.06] focus:shadow-[0_0_20px_rgba(255,255,255,.08)]',
  inputSmall: 'w-full rounded-xl border border-white/10 bg-white/[0.02] px-3.5 py-2.5 text-sm text-white outline-none transition-all duration-300 placeholder:text-white/20 focus:border-white/40 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(255,255,255,.05)]',
  primaryBtn: 'btn-shine rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-black shadow-[0_0_24px_rgba(255,255,255,.2)] transition-all duration-300 hover:bg-gray-100 hover:shadow-[0_0_40px_rgba(255,255,255,.5)] hover:scale-[1.03] active:scale-[0.97] disabled:opacity-55 disabled:pointer-events-none',
  ghostBtn: 'rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white/70 transition-all duration-300 hover:bg-white/15 hover:text-white hover:border-white/20 hover:shadow-[0_0_20px_rgba(255,255,255,.05)] active:scale-[0.97] disabled:opacity-55',
  helpBox: 'rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm leading-relaxed text-white/70 backdrop-blur-[36px] shadow-inner',
  chip: 'rounded-md border border-white/10 bg-white/10 px-2.5 py-1 text-xs leading-none text-white/90 backdrop-blur-md transition-colors hover:bg-white/20 cursor-default',
  greenGlow: 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.9)]',
  redGlow: 'bg-rose-400 shadow-[0_0_12px_rgba(251,113,133,.9)]',
}

const FX = {
  particleDensity: 11000, // Чуть уменьшили для Constellation эффекта (чтобы не перегружать CPU линиями)
  particleMin: 35,
  particleOpacity: 0.7,
}

type ApiResult<T = unknown> = { ok: boolean; data: T | null; error: string | null; code: string | null; meta: Record<string, unknown> }
type AppData = { display_name: string; app_id: string; speech_forms: string[]; enabled: boolean; path?: string; windows_app_id?: string; launch_type?: string; launch_target?: string }
type HistoryItem = { id: string; request_id?: string; raw_text: string; skill: string; confidence: number; result: string; status: 'correct' | 'incorrect' | 'pending'; source?: 'text' | 'voice' | 'overlay'; date: string; args?: Record<string, unknown> }
type SettingsPayload = { text_hotkey_enabled: boolean; text_hotkey_sequence: string; voice: { mode: 'off' | 'hotkey' | 'continuous'; hotkey_enabled: boolean; hotkey_sequence: string; microphone_device: string; agent_names: string[]; require_wake_word_for_continuous: boolean; preload_model_on_startup: boolean; stt: { profile: 'auto' | 'turbo' | 'cpu' | 'accuracy' | 'custom'; model_size: string; device: 'auto' | 'cpu' | 'cuda'; compute_type: 'auto' | 'int8' | 'float16' | 'int8_float16' | 'float32' }; vad: { sensitivity: number; hotkey_silence_ms: number; continuous_silence_ms: number; max_utterance_ms: number } } }

type IconName = 'apps' | 'check' | 'checkCircle' | 'cpu' | 'edit' | 'folder' | 'history' | 'info' | 'keyboard' | 'loader' | 'mic' | 'plus' | 'radio' | 'refresh' | 'rotate' | 'save' | 'search' | 'settings' | 'sliders' | 'terminal' | 'trash' | 'volume' | 'waves' | 'x' | 'xCircle' | 'zap' | 'sparkles'
type IconProps = { name: IconName; size?: number; className?: string }

function Icon({ name, size = 20, className = '' }: IconProps) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, className }
  const paths: Record<IconName, React.ReactNode> = {
    apps: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    check: <path d="M20 6 9 17l-5-5" />,
    checkCircle: <><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-5"/></>,
    cpu: <><rect x="7" y="7" width="10" height="10" rx="2"/><rect x="10" y="10" width="4" height="4"/><path d="M4 9h3M4 15h3M17 9h3M17 15h3M9 4v3M15 4v3M9 17v3M15 17v3"/></>,
    edit: <><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></>,
    folder: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/><path d="M12 7v5l3 2"/></>,
    info: <><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></>,
    keyboard: <><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M8 13h8"/></>,
    loader: <path d="M21 12a9 9 0 1 1-6.2-8.6" />,
    mic: <><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/></>,
    plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
    radio: <><path d="M4.9 19.1a10 10 0 1 1 14.2 0"/><path d="M8.5 15.5a5 5 0 1 1 7 0"/><circle cx="12" cy="12" r="1.5"/></>,
    refresh: <><path d="M21 12a9 9 0 0 1-15.3 6.4"/><path d="M3 12A9 9 0 0 1 18.3 5.6"/><path d="M18 2v4h-4"/><path d="M6 22v-4h4"/></>,
    rotate: <><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/></>,
    save: <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></>,
    search: <><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h.1a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.6 1h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.6 1z"/></>,
    sliders: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/><path d="M2 14h4M10 8h4M18 16h4"/></>,
    terminal: <><path d="m4 17 6-5-6-5"/><path d="M12 19h8"/></>,
    trash: <><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></>,
    volume: <><path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/></>,
    waves: <><path d="M2 12s2-4 5-4 5 8 10 8 5-4 5-4"/><path d="M2 17s2-4 5-4 5 8 10 8 5-4 5-4"/><path d="M2 7s2-4 5-4 5 8 10 8 5-4 5-4"/></>,
    x: <><path d="M18 6 6 18"/><path d="M6 6l12 12"/></>,
    xCircle: <><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></>,
    zap: <path d="M13 2 3 14h8l-1 8 11-14h-8l1-6z" />,
    sparkles: <><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></>,
  }
  return <svg {...common}>{paths[name]}</svg>
}

function Spinner({ size = 18, className = '' }: { size?: number; className?: string }) {
  return <Icon name="loader" size={size} className={`animate-spin ${className}`} />
}

function cloneJson<T>(value: T): T { return JSON.parse(JSON.stringify(value)) }

let mockApps: AppData[] = [
  { display_name: 'Telegram', app_id: 'telegram', speech_forms: ['телега', 'тг', 'телеграм'], enabled: true, path: 'C:\\Program Files\\Telegram\\Telegram.exe' },
  { display_name: 'VS Code', app_id: 'vscode', speech_forms: ['код', 'вс код', 'редактор'], enabled: true, windows_app_id: 'Microsoft.VisualStudioCode' },
  { display_name: 'Chrome', app_id: 'chrome', speech_forms: ['хром', 'браузер'], enabled: true, path: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' },
]

const mockWindowsApps = [
  { display_name: 'Calculator', windows_app_id: 'Microsoft.WindowsCalculator' },
  { display_name: 'Notepad', windows_app_id: 'Microsoft.WindowsNotepad' },
  { display_name: 'Paint', windows_app_id: 'Microsoft.MSPaint' },
  { display_name: 'Discord', windows_app_id: 'Discord' },
]

let mockHistory: HistoryItem[] = [
  { id: 'cmd_101', request_id: 'cmd_101', raw_text: 'открой telegram и vscode пополам', skill: 'window_layout', confidence: 0.95, result: 'Success', status: 'correct', source: 'text', date: new Date(Date.now() - 10000).toISOString(), args: { layout: 'half' } },
  { id: 'cmd_102', request_id: 'cmd_102', raw_text: 'сделай звук потише', skill: 'volume_set', confidence: 0.88, result: 'Volume set to 30%', status: 'correct', source: 'voice', date: new Date(Date.now() - 50000).toISOString(), args: { percent: 30 } },
]

let mockSettings: SettingsPayload = {
  text_hotkey_enabled: true, text_hotkey_sequence: 'Ctrl+Alt+Space',
  voice: {
    mode: 'hotkey', hotkey_enabled: true, hotkey_sequence: 'Ctrl+Alt+V', microphone_device: 'Default Microphone', agent_names: ['бивис', 'beavis'], require_wake_word_for_continuous: true, preload_model_on_startup: false,
    stt: { profile: 'turbo', model_size: 'turbo', device: 'auto', compute_type: 'auto' },
    vad: { sensitivity: 0.012, hotkey_silence_ms: 500, continuous_silence_ms: 700, max_utterance_ms: 7000 },
  },
}

const defaultSettings = cloneJson(mockSettings)
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function beavisCall<T = unknown>(method: string, params: Record<string, any> = {}): Promise<ApiResult<T>> {
  await delay(120 + Math.random() * 140)
  switch (method) {
    case 'system.health': return { ok: true, data: { service: 'beavis_api', status: 'ready' } as T, error: null, code: null, meta: {} }
    case 'commands.run': {
      const item: HistoryItem = { id: `cmd_${Date.now()}`, request_id: `cmd_${Date.now()}`, raw_text: String(params.text || ''), skill: 'mock_skill', confidence: 0.99, result: params.execute === false ? 'ToolCall built' : 'Executed', status: 'pending', source: params.source || 'text', date: new Date().toISOString(), args: { execute: params.execute !== false } }
      mockHistory.unshift(item)
      return { ok: true, data: { raw_text: item.raw_text, skill_prediction: { skill: item.skill, confidence: item.confidence }, execution_result: item.result } as T, error: null, code: null, meta: {} }
    }
    case 'commands.reload': return { ok: true, data: { reloaded: true } as T, error: null, code: null, meta: {} }
    case 'apps.list_user_apps': return { ok: true, data: cloneJson(mockApps) as T, error: null, code: null, meta: {} }
    case 'apps.list_windows_apps': return { ok: true, data: cloneJson(mockWindowsApps) as T, error: null, code: null, meta: {} }
    case 'apps.add': {
      const appId = params.app_id || String(params.display_name || 'app').toLowerCase().replace(/\s+/g, '_')
      if (mockApps.some((app) => app.app_id === appId)) return { ok: false, data: null, error: `App ID уже занят: ${appId}`, code: 'DUPLICATE_APP_ID', meta: {} }
      const forms = (params.speech_forms || []).map((x: string) => x.trim().toLowerCase()).filter(Boolean)
      const usedForm = forms.find((form: string) => mockApps.some((app) => app.speech_forms.includes(form)))
      if (usedForm) return { ok: false, data: null, error: `Фраза уже используется: ${usedForm}`, code: 'DUPLICATE_SPEECH_FORM', meta: {} }
      mockApps.push({ display_name: params.display_name, app_id: appId, speech_forms: forms, enabled: true, path: params.path, windows_app_id: params.windows_app_id })
      return { ok: true, data: { added: true } as T, error: null, code: null, meta: {} }
    }
    case 'apps.update_speech_forms': {
      const forms = (params.speech_forms || []).map((x: string) => x.trim().toLowerCase()).filter(Boolean)
      const usedForm = forms.find((form: string) => mockApps.some((app) => app.app_id !== params.app_id && app.speech_forms.includes(form)))
      if (usedForm) return { ok: false, data: null, error: `Фраза уже используется в другом приложении: ${usedForm}`, code: 'DUPLICATE_SPEECH_FORM', meta: {} }
      mockApps = mockApps.map((app) => app.app_id === params.app_id ? { ...app, speech_forms: forms } : app)
      return { ok: true, data: { updated: true } as T, error: null, code: null, meta: {} }
    }
    case 'apps.delete': mockApps = mockApps.filter((app) => app.app_id !== params.app_id); return { ok: true, data: { deleted: true } as T, error: null, code: null, meta: {} }
    case 'apps.apply_changes': {
      const changes = Array.isArray(params.changes) ? params.changes : []
      for (const change of changes) {
        if (change.operation === 'delete') {
          mockApps = mockApps.filter((app) => app.app_id !== change.app_id)
        } else if (change.operation === 'add') {
          mockApps.push({
            display_name: change.display_name || change.app_id,
            app_id: change.app_id,
            speech_forms: change.speech_forms || [],
            enabled: true,
            path: change.path,
            windows_app_id: change.windows_app_id,
            launch_type: change.launch_type,
            launch_target: change.launch_target,
          })
        } else if (change.operation === 'update_speech_forms') {
          mockApps = mockApps.map((app) => app.app_id === change.app_id ? {
            ...app,
            display_name: change.display_name || app.display_name,
            speech_forms: change.speech_forms || app.speech_forms,
            path: change.path ?? app.path,
            windows_app_id: change.windows_app_id ?? app.windows_app_id,
            launch_type: change.launch_type ?? app.launch_type,
            launch_target: change.launch_target ?? app.launch_target,
          } : app)
        } else if (change.operation === 'disable') {
          mockApps = mockApps.map((app) => app.app_id === change.app_id ? { ...app, enabled: false } : app)
        } else if (change.operation === 'enable') {
          mockApps = mockApps.map((app) => app.app_id === change.app_id ? { ...app, enabled: true } : app)
        }
      }
      return { ok: true, data: { applied: true, count: changes.length } as T, error: null, code: null, meta: {} }
    }
    case 'settings.load': return { ok: true, data: cloneJson(mockSettings) as T, error: null, code: null, meta: {} }
    case 'settings.save': mockSettings = cloneJson(params) as SettingsPayload; return { ok: true, data: { saved: true } as T, error: null, code: null, meta: {} }
    case 'history.list': return { ok: true, data: cloneJson(mockHistory.slice(0, params.limit || 120)) as T, error: null, code: null, meta: {} }
    case 'history.mark': mockHistory = mockHistory.map((item) => item.id === params.request_id || item.request_id === params.request_id ? { ...item, status: params.status } : item); return { ok: true, data: { marked: true } as T, error: null, code: null, meta: {} }
    case 'voice.preload': return { ok: true, data: { preloaded: true } as T, error: null, code: null, meta: {} }
    case 'voice.test_microphone': return { ok: true, data: { transcript: 'бивис тестовая проверка микрофона' } as T, error: null, code: null, meta: {} }
    case 'voice.listen_once': return { ok: true, data: { command_text: 'открой telegram', transcript: 'бивис открой telegram', meta: { source: 'voice' } } as T, error: null, code: null, meta: {} }
    default: return { ok: false, data: null, error: `Method not mocked: ${method}`, code: 'NOT_FOUND', meta: {} }
  }
}

async function runSmokeTests() {
  console.assert((await beavisCall('system.health')).ok, 'system.health ok')
}

// === TOAST SYSTEM ===
type Toast = { id: string; message: string; type: 'success' | 'error' | 'info' }
const ToastContext = React.createContext<{ showToast: (message: string, type?: Toast['type']) => void }>({ showToast: () => {} })
function useToast() { return React.useContext(ToastContext) }

function ToastHost({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const showToast = (message: string, type: Toast['type'] = 'info') => {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((toast) => toast.id !== id)), 3200)
  }
  return <ToastContext.Provider value={{ showToast }}>{children}<div className="fixed bottom-[80px] md:bottom-5 right-5 z-[1000] flex flex-col gap-3">{toasts.map((toast) => <div key={toast.id} className={`toast-in flex items-center gap-3 rounded-2xl border px-5 py-3.5 text-sm font-medium shadow-[0_15px_40px_rgba(0,0,0,0.5)] backdrop-blur-xl ${toast.type === 'success' ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-100' : toast.type === 'error' ? 'border-rose-500/30 bg-rose-500/15 text-rose-100' : 'border-white/15 bg-white/10 text-white'}`}>{toast.type === 'success' && <Icon name="checkCircle" size={18} className="text-emerald-400"/>}{toast.type === 'error' && <Icon name="xCircle" size={18} className="text-rose-400"/>}{toast.type === 'info' && <Icon name="zap" size={18} className="text-blue-300"/>}{toast.message}</div>)}</div></ToastContext.Provider>
}

// === UI COMPONENTS ===
function Toggle({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return <button type="button" onClick={() => onChange(!checked)} className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-all duration-300 ${checked ? 'border-white/50 bg-white/90 shadow-[0_0_15px_rgba(255,255,255,.4)]' : 'border-white/10 bg-black/50'}`}><span className={`h-5 w-5 rounded-full transition-all duration-300 shadow-sm ${checked ? 'translate-x-6 bg-black' : 'translate-x-1 bg-white/50'}`} /></button>
}

function GlassInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${THEME.input} ${props.className ?? ''}`} />
}

function NumberField({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return <input inputMode="numeric" value={String(value)} onChange={(e) => onChange(Number(e.target.value.replace(/[^0-9.]/g, '')) || 0)} className={`${THEME.inputSmall} h-[42px]`} />
}

type SelectOption = { value: string; label: string }
function GlassDropdown({ value, options, onChange }: { value: string; options: SelectOption[]; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const current = options.find((item) => item.value === value)?.label || value

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false) }
    const esc = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', close); window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('mousedown', close); window.removeEventListener('keydown', esc) }
  }, [open])

  return <div ref={rootRef} className={`relative ${open ? 'z-[300]' : 'z-0'}`}>
    <button type="button" onClick={() => setOpen((next) => !next)} className="glass-dropdown-trigger flex h-[46px] w-full items-center justify-between rounded-xl px-4 py-3 text-left text-sm text-white outline-none transition-all">
      <span>{current}</span><span className="text-white/50 opacity-60 transition-transform duration-200" style={{ transform: open ? 'rotate(180deg)' : 'none' }}>▼</span>
    </button>
    {open && <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-[300] max-h-[210px] overflow-y-auto rounded-xl border border-white/20 bg-[#080808] p-1.5 shadow-[0_30px_80px_rgba(0,0,0,1),0_0_0_1px_rgba(255,255,255,.05)] custom-scrollbar dropdown-in">
      <div className="space-y-0.5">{options.map((item) => <button key={item.value} type="button" onClick={() => { onChange(item.value); setOpen(false) }} className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-all ${item.value === value ? 'bg-white/15 text-white font-medium' : 'text-white/60 hover:bg-white/10 hover:text-white'}`}>{item.label}</button>)}</div>
    </div>}
  </div>
}

function Field({ label, hint, info, children }: { label: string; hint?: string; info?: string; children: React.ReactNode }) {
  return <label className="block"><div className="mb-2 flex items-center justify-between gap-4">{info ? <span className="group relative inline-flex items-center text-[11px] font-bold uppercase tracking-[0.15em] text-white/50">{label}<span className="pointer-events-none absolute left-0 bottom-[calc(100%+8px)] z-[600] w-64 rounded-xl border border-white/15 bg-zinc-900 px-3 py-2.5 text-xs font-normal normal-case leading-relaxed tracking-normal text-white/90 opacity-0 shadow-[0_20px_50px_rgba(0,0,0,.95)] transition-opacity duration-200 group-hover:opacity-100">{info}</span></span> : <span className="inline-flex items-center text-[11px] font-bold uppercase tracking-[0.15em] text-white/50">{label}</span>}{hint && <span className="text-[11px] font-medium text-white/30">{hint}</span>}</div>{children}</label>
}

function SectionCard({ icon, title, subtitle, children, delayClass = '' }: { icon: IconName; title: string; subtitle?: string; children: React.ReactNode; delayClass?: string }) {
  return <section className={`${THEME.surface} ${THEME.surfaceHover} p-5 md:p-6 page-enter ${delayClass}`}><div className="mb-6 flex items-start gap-4"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-white/5 shadow-[inset_0_1px_1px_rgba(255,255,255,.1)] transition-colors group-hover:bg-white/10 text-white/80"><Icon name={icon} size={22}/></div><div><h3 className="text-xl font-semibold text-white tracking-tight">{title}</h3>{subtitle && <p className="mt-1 text-sm text-white/50">{subtitle}</p>}</div></div><div className="space-y-6">{children}</div></section>
}

// === ENHANCED PARTICLE FX (CONSTELLATION + SHOCKWAVE) ===
function ParticleStorm() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  
  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    
    let width = canvas.width = window.innerWidth
    let height = canvas.height = window.innerHeight
    let frame = 0
    let animationId = 0
    let mouse = { x: -1000, y: -1000 }
    let shockwaves: {x: number, y: number, radius: number, alpha: number}[] = []
    
    let particles = makeParticles(width, height)
    function makeParticles(w: number, h: number) {
      return Array.from({ length: Math.max(FX.particleMin, Math.floor((w * h) / FX.particleDensity)) }, () => ({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - 0.5) * 0.8, vy: (Math.random() - 0.5) * 0.8, size: Math.random() * 1.5 + 0.5, phase: Math.random() * Math.PI * 2 }))
    }
    
    const resize = () => { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; particles = makeParticles(width, height) }
    window.addEventListener('resize', resize)
    
    const onMouseMove = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; }
    const onMouseLeave = () => { mouse.x = -1000; mouse.y = -1000; }
    const onClick = (e: MouseEvent) => { shockwaves.push({ x: e.clientX, y: e.clientY, radius: 0, alpha: 1 }) }
    
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseout', onMouseLeave)
    window.addEventListener('click', onClick)
    
    const animate = () => {
      frame += 0.015
      ctx.clearRect(0, 0, width, height) // Clear instead of fill for better blending if needed
      
      // Update shockwaves
      for (let i = shockwaves.length - 1; i >= 0; i--) {
        let sw = shockwaves[i];
        sw.radius += 12;
        sw.alpha -= 0.02;
        if (sw.alpha <= 0) shockwaves.splice(i, 1);
        else {
          ctx.beginPath();
          ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(255,255,255,${sw.alpha * 0.3})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      // Constellation & Movement
      for (let i = 0; i < particles.length; i++) {
        let p = particles[i]
        p.x += p.vx; p.y += p.vy + Math.sin(frame + p.phase) * 0.1
        
        // Mouse Repulsion
        let dxMouse = mouse.x - p.x; let dyMouse = mouse.y - p.y;
        let distMouse = Math.sqrt(dxMouse*dxMouse + dyMouse*dyMouse);
        if (distMouse < 150) { p.x -= dxMouse * 0.02; p.y -= dyMouse * 0.02; }

        // Shockwave displacement
        for (let sw of shockwaves) {
          let dxSW = sw.x - p.x; let dySW = sw.y - p.y;
          let distSW = Math.sqrt(dxSW*dxSW + dySW*dySW);
          if (Math.abs(distSW - sw.radius) < 30) {
             p.x -= dxSW * 0.05; p.y -= dySW * 0.05;
          }
        }

        // Screen Wrap
        if (p.x > width + 20) p.x = -20; if (p.y > height + 20) p.y = -20;
        if (p.x < -20) p.x = width + 20; if (p.y < -20) p.y = height + 20;
        
        // Draw Lines to nearby particles (Constellation)
        for (let j = i + 1; j < particles.length; j++) {
           let p2 = particles[j];
           let dx = p.x - p2.x; let dy = p.y - p2.y;
           let distSq = dx*dx + dy*dy;
           if (distSq < 12000) { // approx 110px distance
              let alpha = 0.15 - (distSq / 12000) * 0.15;
              ctx.beginPath();
              ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y);
              ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
              ctx.lineWidth = 0.6;
              ctx.stroke();
           }
        }
        
        const baseAlpha = Math.max(0.1, Math.sin(frame * 2 + p.phase) * 0.3 + 0.3)
        const finalAlpha = distMouse < 150 ? Math.min(1, baseAlpha + 0.5) : baseAlpha;

        ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2); 
        ctx.fillStyle = `rgba(255,255,255,${finalAlpha})`; 
        ctx.shadowBlur = distMouse < 150 ? 15 : 5; 
        ctx.shadowColor = 'rgba(255,255,255,.5)'; 
        ctx.fill(); ctx.shadowBlur = 0
      }
      animationId = requestAnimationFrame(animate)
    }
    animate()
    return () => { 
      window.removeEventListener('resize', resize); 
      window.removeEventListener('mousemove', onMouseMove); 
      window.removeEventListener('mouseout', onMouseLeave); 
      window.removeEventListener('click', onClick);
      cancelAnimationFrame(animationId) 
    }
  }, [])
  return <canvas ref={canvasRef} className="fixed inset-0 z-0 pointer-events-none" style={{ opacity: FX.particleOpacity }} />
}

// === HOOKS ===
// Typewriter effect for input placeholders
function useTypewriter(phrases: string[], speed = 60, pause = 2000) {
  const [text, setText] = useState('');
  const [index, setIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentPhrase = phrases[index % phrases.length];
    let timer: any;
    
    if (isDeleting) {
      timer = setTimeout(() => {
        setText(currentPhrase.substring(0, text.length - 1));
        if (text.length === 0) { setIsDeleting(false); setIndex((i) => i + 1); }
      }, speed / 2);
    } else {
      timer = setTimeout(() => {
        setText(currentPhrase.substring(0, text.length + 1));
        if (text.length === currentPhrase.length) {
          timer = setTimeout(() => setIsDeleting(true), pause);
        }
      }, speed);
    }
    return () => clearTimeout(timer);
  }, [text, isDeleting, index, phrases, speed, pause]);

  return text;
}


// === PAGES ===
function HomePage({ openVoice }: { openVoice: () => void }) {
  const [query, setQuery] = useState('')
  const [execute, setExecute] = useState(true)
  const [isExecuting, setIsExecuting] = useState(false)
  const { showToast } = useToast()
  
  const placeholders = useMemo(() => ["открой telegram и vscode пополам", "сделай звук тише на 30%", "создай новый файл", "запусти браузер"], []);
  const placeholderText = useTypewriter(placeholders);

  const run = async (event?: React.FormEvent) => {
    event?.preventDefault()
    if (!query.trim()) return
    setIsExecuting(true)
    const res = await beavisCall('commands.run', { text: query, execute, source: 'text' })
    setIsExecuting(false)
    if (res.ok) { setQuery(''); showToast(execute ? 'Команда выполнена' : 'ToolCall построен', 'success') }
    else showToast(res.error || 'Ошибка', 'error')
  }

  return <div className="flex min-h-[80vh] flex-col items-center justify-center px-4"><h1 className="mb-10 md:mb-14 text-4xl md:text-[5rem] md:leading-[1.1] font-semibold tracking-tight text-white drop-shadow-[0_0_40px_rgba(255,255,255,.3)] text-center">Что сделать?</h1><div className="group relative w-full max-w-3xl"><div className="absolute -inset-2 rounded-[3rem] bg-gradient-to-r from-white/10 via-white/5 to-white/10 opacity-30 blur-2xl transition duration-700 group-hover:opacity-70 group-focus-within:opacity-100 group-focus-within:bg-gradient-to-r group-focus-within:from-white/20 group-focus-within:to-white/20"/><form onSubmit={run} className="relative flex flex-col md:flex-row items-center rounded-[2.5rem] md:rounded-[3rem] border border-white/[0.15] bg-[#08080a]/60 md:bg-white/[0.03] p-2 md:pr-3 shadow-[0_15px_50px_0_rgba(0,0,0,.8),inset_0_1px_1px_rgba(255,255,255,.1)] backdrop-blur-[60px] transition-all duration-500 focus-within:border-white/[0.4] focus-within:bg-[#0a0a0c]/80"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={placeholderText + '|'} disabled={isExecuting} className="w-full md:flex-1 border-none bg-transparent px-6 py-5 md:px-8 md:py-6 text-lg md:text-2xl font-light text-white outline-none placeholder:text-white/30 text-center md:text-left transition-all"/><div className="flex items-center gap-2 w-full md:w-auto justify-center pb-3 md:pb-0"><button type="button" onClick={openVoice} className="rounded-full p-4 text-white/50 transition-all duration-300 hover:bg-white/10 hover:text-white hover:scale-110 active:scale-95"><Icon name="mic" size={26}/></button><button type="submit" disabled={isExecuting || !query.trim()} className="btn-shine flex items-center gap-2 rounded-[2rem] bg-white px-8 py-4 font-semibold text-black shadow-[0_0_30px_rgba(255,255,255,.25)] transition-all duration-300 hover:bg-gray-100 hover:shadow-[0_0_50px_rgba(255,255,255,.5)] active:scale-95 disabled:opacity-50"><Icon name="sparkles" size={18}/> {isExecuting ? <Spinner size={22}/> : 'Выполнить'}</button></div></form></div><div className="mt-10 flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm text-white/60 backdrop-blur-2xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] transition-colors hover:bg-white/10"><Toggle checked={execute} onChange={setExecute}/><span>{execute ? 'Выполнять действие' : 'Только распознать'}</span></div></div>
}


function appsEqual(a: AppData, b: AppData) {
  return a.display_name === b.display_name && a.app_id === b.app_id && (a.path || '') === (b.path || '') && (a.windows_app_id || '') === (b.windows_app_id || '') && JSON.stringify(a.speech_forms || []) === JSON.stringify(b.speech_forms || [])
}

function buildAppChanges(originalApps: AppData[], draftApps: AppData[]) {
  const changes: any[] = []
  const originalById = new Map(originalApps.map((app) => [app.app_id, app]))
  const draftById = new Map(draftApps.map((app) => [app.app_id, app]))

  for (const original of originalApps) {
    if (!draftById.has(original.app_id)) changes.push({ operation: 'delete', app_id: original.app_id })
  }

  for (const draft of draftApps) {
    const original = originalById.get(draft.app_id)
    if (!original) {
      changes.push({ operation: 'add', source: 'ui', app_id: draft.app_id, display_name: draft.display_name, speech_forms: draft.speech_forms, path: draft.path, windows_app_id: draft.windows_app_id, launch_type: draft.launch_type, launch_target: draft.launch_target })
    } else if (!appsEqual(original, draft)) {
      changes.push({ operation: 'update_speech_forms', source: 'ui', app_id: draft.app_id, display_name: draft.display_name, speech_forms: draft.speech_forms, path: draft.path, windows_app_id: draft.windows_app_id, launch_type: draft.launch_type, launch_target: draft.launch_target })
    }
  }
  return changes
}

function AppModal({ isOpen, onClose, appToEdit, onSaveDraft, apps }: { isOpen: boolean; onClose: () => void; appToEdit?: AppData | null; onSaveDraft: (app: AppData) => void; apps: AppData[] }) {
  const [mode, setMode] = useState<'path' | 'windows'>('path')
  const [displayName, setDisplayName] = useState('')
  const [appId, setAppId] = useState('')
  const [path, setPath] = useState('')
  const [winAppId, setWinAppId] = useState('')
  const [speechForms, setSpeechForms] = useState<string[]>([])
  const [newSlang, setNewSlang] = useState('')
  const [windowsApps, setWindowsApps] = useState<any[]>([])
  const [winSearch, setWinSearch] = useState('')
  const slangBoxRef = useRef<HTMLDivElement>(null)
  const [draggingSlang, setDraggingSlang] = useState<string | null>(null)
  const { showToast } = useToast()

  useEffect(() => {
    if (!isOpen) return
    setDisplayName(appToEdit?.display_name || '')
    setAppId(appToEdit?.app_id || '')
    setPath(appToEdit?.path || '')
    setWinAppId(appToEdit?.windows_app_id || '')
    setSpeechForms(appToEdit?.speech_forms || [])
    setNewSlang('')
    setMode(appToEdit?.windows_app_id ? 'windows' : 'path')
    beavisCall<any[]>('apps.list_windows_apps').then((res) => res.ok && res.data && setWindowsApps(res.data))
  }, [isOpen, appToEdit])

  if (!isOpen) return null

  const normalizedAppId = appId.trim().toLowerCase()
  const duplicateAppId = !appToEdit && apps.some((app) => app.app_id === normalizedAppId)
  const duplicateSpeech = speechForms.find((form) => apps.some((app) => app.app_id !== appToEdit?.app_id && app.speech_forms.includes(form)))

  const addSlang = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return
    event.preventDefault()
    const value = newSlang.trim().toLowerCase()
    if (!value) return
    if (speechForms.includes(value)) return showToast('Такая фраза уже есть у этого приложения', 'error')
    const owner = apps.find((app) => app.app_id !== appToEdit?.app_id && app.speech_forms.includes(value))
    if (owner) return showToast(`Фраза уже используется в ${owner.display_name}`, 'error')
    setSpeechForms((prev) => [...prev, value])
    setNewSlang('')
  }

  const removeSpeechForm = (form: string) => setSpeechForms((prev) => prev.filter((item) => item !== form))
  const handleSlangDragEnd = (form: string, event: React.DragEvent<HTMLSpanElement>) => {
    const box = slangBoxRef.current?.getBoundingClientRect()
    const insideBox = Boolean(box && event.clientX >= box.left && event.clientX <= box.right && event.clientY >= box.top && event.clientY <= box.bottom)
    setDraggingSlang(null)
    if (!insideBox) { removeSpeechForm(form); showToast(`Фраза удалена: ${form}`, 'info') }
  }

  const saveDraft = () => {
    if (!displayName.trim() || !normalizedAppId) return showToast('Заполните имя и app_id', 'error')
    if (duplicateAppId) return showToast(`App ID уже занят: ${normalizedAppId}`, 'error')
    if (duplicateSpeech) return showToast(`Фраза уже используется в другом приложении: ${duplicateSpeech}`, 'error')
    onSaveDraft({
      display_name: displayName.trim(),
      app_id: normalizedAppId,
      speech_forms: speechForms,
      enabled: true,
      path: mode === 'path' ? path : undefined,
      windows_app_id: mode === 'windows' ? winAppId : undefined,
      launch_type: mode === 'windows' ? 'apps_folder' : undefined,
      launch_target: mode === 'windows' ? winAppId : undefined,
    })
    showToast('Изменение добавлено в черновик', 'success')
    onClose()
  }

  const filteredWinApps = windowsApps.filter((app) => app.display_name.toLowerCase().includes(winSearch.toLowerCase()))

  return <div className="fixed inset-0 z-[100] flex min-h-screen items-center justify-center overflow-hidden bg-black/80 p-4 md:p-6 backdrop-blur-xl transition-opacity"><div className={`${THEME.surface} max-h-[calc(100vh-48px)] w-full max-w-xl overflow-y-auto p-6 md:p-8 custom-scrollbar scale-100 page-enter`}><div className="mb-6 flex items-center justify-between"><h2 className="text-2xl font-light text-white">{appToEdit ? 'Изменить приложение' : 'Новое приложение'}</h2><button onClick={onClose} className="rounded-full bg-white/[0.06] p-2 text-white/40 transition hover:text-white hover:bg-white/15 active:scale-95"><Icon name="x" size={20}/></button></div>{!appToEdit && <div className="relative mb-6 grid grid-cols-2 overflow-hidden rounded-2xl border border-white/[0.1] bg-[#050505] p-1.5">
    <div className="absolute bottom-1.5 top-1.5 rounded-xl bg-white shadow-[0_0_28px_rgba(255,255,255,.35)] transition-all duration-500 ease-out" style={{ left: mode === 'path' ? '6px' : 'calc(50% + 0px)', width: 'calc(50% - 6px)' }}/>
    <button type="button" onClick={() => setMode('path')} className={`relative z-10 rounded-xl px-3 py-3 text-sm font-semibold transition-colors duration-300 ${mode === 'path' ? 'text-black' : 'text-white/50 hover:text-white/75'}`}>По пути</button>
    <button type="button" onClick={() => setMode('windows')} className={`relative z-10 rounded-xl px-3 py-3 text-sm font-semibold transition-colors duration-300 ${mode === 'windows' ? 'text-black' : 'text-white/50 hover:text-white/75'}`}>Из Windows</button>
  </div>}<div className="space-y-5">{mode === 'path' ? <Field label="Путь к файлу"><div className="relative"><Icon name="folder" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30"/><GlassInput value={path} onChange={(e) => setPath(e.target.value)} placeholder="C:\\Program Files\\App\\app.exe" className="pl-10 font-mono"/></div></Field> : <Field label="Windows приложение"><div className="relative mb-2"><Icon name="search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30"/><GlassInput value={winSearch} onChange={(e) => setWinSearch(e.target.value)} placeholder="Поиск в системе..." className="pl-10"/></div><div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-white/10 bg-[#080808]/80 p-1 custom-scrollbar shadow-inner">{filteredWinApps.map((app) => <button key={app.windows_app_id} onClick={() => { setWinAppId(app.windows_app_id); setDisplayName(app.display_name); setAppId(app.display_name.toLowerCase().replace(/\s+/g, '_')) }} className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-all ${winAppId === app.windows_app_id ? 'bg-white/15 text-white shadow-md' : 'text-white/60 hover:bg-white/10 hover:text-white'}`}>{app.display_name}<span className="ml-2 font-mono text-xs opacity-40">{app.windows_app_id}</span></button>)}</div></Field>}<div className="grid grid-cols-1 gap-4 md:grid-cols-2"><Field label="Имя"><GlassInput value={displayName} onChange={(e) => setDisplayName(e.target.value)}/></Field><Field label="App ID"><GlassInput value={appId} onChange={(e) => setAppId(e.target.value.toLowerCase().replace(/\s+/g, '_'))} className={`font-mono ${duplicateAppId ? 'border-red-400/50' : ''}`}/>{duplicateAppId && <div className="mt-1 text-xs text-red-300/80">Такой app_id уже занят</div>}</Field></div><Field label="Сленг и фразы" hint="Enter / вынеси чип за строку"><div ref={slangBoxRef} className={`flex min-h-[48px] flex-wrap items-center gap-1.5 rounded-xl border p-2 transition-all ${draggingSlang ? 'border-red-300/35 bg-red-500/[0.06]' : 'border-white/10 bg-[#050505]/60'}`}>{speechForms.map((form) => <span key={form} draggable onDragStart={() => setDraggingSlang(form)} onDragEnd={(e) => handleSlangDragEnd(form, e)} className={`flex h-8 cursor-grab select-none items-center rounded-md border px-2.5 text-xs text-white/90 transition active:cursor-grabbing ${draggingSlang === form ? 'scale-95 border-red-300/35 bg-red-500/15 opacity-70' : 'border-white/10 bg-white/[0.105] hover:border-white/20 hover:bg-white/[0.15]'}`}><span>{form}</span></span>)}<input value={newSlang} onChange={(e) => setNewSlang(e.target.value)} onKeyDown={addSlang} placeholder={draggingSlang ? 'Отпусти вне строки — удалится' : 'Добавить...'} className="min-w-[110px] flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/25"/></div>{duplicateSpeech && <div className="mt-1 text-xs text-red-300/80">Фраза уже используется: {duplicateSpeech}</div>}</Field></div><div className="mt-8 flex justify-end gap-3"><button onClick={onClose} className="px-5 py-2.5 text-sm font-medium text-white/50 transition hover:text-white active:scale-95">Отмена</button><button onClick={saveDraft} className={`${THEME.primaryBtn} flex items-center gap-2`}><Icon name="check" size={16}/>В черновик</button></div></div></div>
}

function AppsPage() {
  const [originalApps, setOriginalApps] = useState<AppData[]>([])
  const [draftApps, setDraftApps] = useState<AppData[]>([])
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(false)
  const [search, setSearch] = useState('')
  const [isModalOpen, setModalOpen] = useState(false)
  const [editApp, setEditApp] = useState<AppData | null>(null)
  const { showToast } = useToast()
  const pendingChanges = useMemo(() => buildAppChanges(originalApps, draftApps), [originalApps, draftApps])
  const hasDraft = pendingChanges.length > 0

  const loadApps = async () => {
    setLoading(true)
    const res = await beavisCall<AppData[]>('apps.list_user_apps')
    if (res.ok && res.data) { setOriginalApps(cloneJson(res.data)); setDraftApps(cloneJson(res.data)) }
    setLoading(false)
  }
  useEffect(() => { loadApps() }, [])

  const saveDraftApp = (app: AppData) => {
    setDraftApps((prev) => {
      const exists = prev.some((item) => item.app_id === app.app_id)
      return exists ? prev.map((item) => item.app_id === app.app_id ? app : item) : [...prev, app]
    })
  }
  const deleteDraftApp = (appId: string) => {
    setDraftApps((prev) => prev.filter((app) => app.app_id !== appId))
    showToast('Удаление добавлено в черновик', 'info')
  }
  const resetDraft = () => { setDraftApps(cloneJson(originalApps)); showToast('Черновик сброшен', 'info') }
  const applyDraft = async () => {
    if (!pendingChanges.length) return
    setApplying(true)
    const res = await beavisCall('apps.apply_changes', { changes: pendingChanges, retrain: true })
    if (res.ok) {
      await beavisCall('commands.reload')
      showToast('Изменения применены, pipeline обновлён', 'success')
      await loadApps()
    } else showToast(res.error || 'Ошибка применения', 'error')
    setApplying(false)
  }

  const filteredApps = draftApps.filter((app) => app.display_name.toLowerCase().includes(search.toLowerCase()) || app.speech_forms.some((form) => form.includes(search.toLowerCase())))

  return <div className={THEME.page}><div className="mb-8 flex flex-col items-start justify-between gap-4 md:flex-row md:items-center"><div><h2 className="mb-2 text-3xl font-light text-white tracking-tight">Приложения</h2><p className="text-sm text-white/40">Настройка программ и их распознавания</p></div><div className="flex w-full flex-wrap md:flex-nowrap items-center gap-3 md:w-auto"><div className="relative flex-1 md:w-64 min-w-[200px]"><Icon name="search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"/><GlassInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Поиск..." className="pl-10"/></div><button onClick={loadApps} className={THEME.ghostBtn}><Icon name="refresh" size={18}/></button><button onClick={() => { setEditApp(null); setModalOpen(true) }} className={`${THEME.primaryBtn} flex items-center gap-2`}><Icon name="plus" size={18}/><span className="hidden sm:inline">Добавить</span></button></div></div>
    {hasDraft && <div className="mb-6 flex flex-col gap-4 rounded-[24px] border border-white/10 bg-[#0c0c0e]/80 p-4 shadow-[0_18px_55px_rgba(0,0,0,.4),inset_0_1px_1px_rgba(255,255,255,.05)] backdrop-blur-[46px] md:flex-row md:items-center md:justify-between page-enter"><div><div className="flex items-center gap-2 text-sm font-semibold text-white"><Icon name="sparkles" size={16} className="text-white/70"/>Черновик изменений</div><div className="mt-1 text-xs text-white/45">{pendingChanges.length} измен. — применить, чтобы сохранить и запустить переобучение.</div></div><div className="flex flex-wrap gap-2"><button onClick={resetDraft} className={`${THEME.ghostBtn} flex items-center gap-2`}><Icon name="rotate" size={16}/>Сбросить</button><button onClick={applyDraft} disabled={applying} className={`${THEME.primaryBtn} flex items-center gap-2`}>{applying ? <Spinner size={16}/> : <Icon name="check" size={16}/>}Применить</button></div></div>}
    {loading ? <div className="flex justify-center p-20"><Spinner size={40} className="text-white/50"/></div> : <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{filteredApps.map((app, index) => {
      const original = originalApps.find((item) => item.app_id === app.app_id)
      const isNew = !original
      const isChanged = Boolean(original && !appsEqual(original, app))
      return <div key={app.app_id} className={`${THEME.surface} ${THEME.surfaceHover} group p-6 page-enter stagger-${(index % 5) + 1} ${isNew ? 'border-emerald-400/25' : isChanged ? 'border-yellow-300/25' : ''}`}><div className="relative z-10 mb-5 flex items-start justify-between"><div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/5 shadow-inner transition-colors group-hover:bg-white/10 group-hover:shadow-[0_0_20px_rgba(255,255,255,0.1)] text-white/80"><Icon name="apps" size={22}/></div><div className="flex translate-x-2 gap-2 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100"><button onClick={() => { setEditApp(app); setModalOpen(true) }} className="rounded-full bg-[#050505] p-2 text-white/50 shadow-md transition hover:bg-white/20 hover:text-white"><Icon name="edit" size={14}/></button><button onClick={() => deleteDraftApp(app.app_id)} className="rounded-full bg-[#050505] p-2 text-white/50 shadow-md transition hover:bg-red-500/30 hover:text-red-400"><Icon name="trash" size={14}/></button></div></div><div className="mb-1 flex items-center gap-2"><h3 className="text-xl font-semibold text-white tracking-tight">{app.display_name}</h3>{isNew && <span className="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-emerald-200">new</span>}{isChanged && <span className="rounded-md border border-yellow-300/20 bg-yellow-300/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-yellow-100">draft</span>}</div><p className="mb-5 truncate font-mono text-xs text-white/30">{app.path || app.windows_app_id || app.app_id}</p><div className="flex flex-wrap gap-1.5">{app.speech_forms.slice(0, 4).map((form) => <span key={form} className={THEME.chip}>{form}</span>)}{app.speech_forms.length > 4 && <span className="rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-white/40">+{app.speech_forms.length - 4}</span>}</div></div>
    })}</div>}<AppModal isOpen={isModalOpen} onClose={() => setModalOpen(false)} appToEdit={editApp} onSaveDraft={saveDraftApp} apps={draftApps}/></div>
}

function HistoryPage() {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [selected, setSelected] = useState<HistoryItem | null>(null)
  const [filter, setFilter] = useState('')
  const { showToast } = useToast()
  
  const load = async () => { const res = await beavisCall<HistoryItem[]>('history.list', { limit: 120 }); if (res.ok && res.data) setHistory(res.data) }
  useEffect(() => { load() }, [])
  const mark = async (item: HistoryItem, status: 'correct' | 'incorrect') => { await beavisCall('history.mark', { request_id: item.request_id || item.id, status }); showToast('Оценка сохранена', 'success'); setHistory((prev) => prev.map((h) => h.id === item.id ? { ...h, status } : h)) }
  const filtered = history.filter((item) => item.raw_text.toLowerCase().includes(filter.toLowerCase()) || item.skill.toLowerCase().includes(filter.toLowerCase()))
  
  return <div className={THEME.pageNarrow}><div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><h2 className="mb-2 text-3xl font-light text-white tracking-tight">История команд</h2><p className="text-sm text-white/40">Логи команд, результаты и оценка качества</p></div><div className="relative w-full md:w-72"><Icon name="search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"/><GlassInput value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Фильтр..." className="pl-10"/></div></div><div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]"><div className={`${THEME.surface} overflow-hidden max-h-[600px] flex flex-col shadow-[0_20px_60px_rgba(0,0,0,0.5)]`}><div className="overflow-x-auto custom-scrollbar flex-1"><table className="w-full border-collapse text-left min-w-[500px]"><thead className="sticky top-0 bg-[#0a0a0c] z-10 backdrop-blur-xl"><tr className="border-b border-white/10 shadow-[0_4px_10px_rgba(0,0,0,0.2)]"><th className="p-4 md:p-5 text-xs font-semibold uppercase tracking-wider text-white/50">Время</th><th className="p-4 md:p-5 text-xs font-semibold uppercase tracking-wider text-white/50">Команда</th><th className="p-4 md:p-5 text-xs font-semibold uppercase tracking-wider text-white/50">Навык</th><th className="p-4 md:p-5 text-right text-xs font-semibold uppercase tracking-wider text-white/50">Оценка</th></tr></thead><tbody>{filtered.map((item, i) => <tr key={item.id} onClick={() => setSelected(item)} className={`group cursor-pointer border-b border-white/[0.03] transition-colors hover:bg-white/[0.05] page-enter stagger-${(i % 5) + 1} ${selected?.id === item.id ? 'bg-white/[0.06] border-l-2 border-l-white/40' : 'border-l-2 border-l-transparent'}`}><td className="whitespace-nowrap p-4 md:p-5 text-sm text-white/50">{new Date(item.date).toLocaleTimeString()}</td><td className="p-4 md:p-5 font-semibold text-white/90">{item.raw_text}<div className="mt-1 font-mono text-xs text-white/30 truncate max-w-[200px] md:max-w-[300px]">{item.result}</div></td><td className="p-4 md:p-5 text-sm text-white/60"><span className="rounded-md border border-white/10 bg-black/40 px-2.5 py-1 text-xs shadow-inner">{item.skill}</span></td><td className="p-4 md:p-5 text-right"><div className={`flex items-center justify-end gap-2 transition-opacity ${item.status === 'pending' ? 'opacity-0 group-hover:opacity-100' : 'opacity-100'}`}><button onClick={(e) => { e.stopPropagation(); mark(item, 'correct') }} className={`rounded-lg p-2 transition-all hover:scale-110 active:scale-95 ${item.status === 'correct' ? 'border border-green-500/30 bg-green-500/10 text-green-400' : 'text-white/40 hover:bg-white/10 hover:text-white'}`}><Icon name="check" size={16}/></button><button onClick={(e) => { e.stopPropagation(); mark(item, 'incorrect') }} className={`rounded-lg p-2 transition-all hover:scale-110 active:scale-95 ${item.status === 'incorrect' ? 'border border-red-500/30 bg-red-500/10 text-red-400' : 'text-white/40 hover:bg-white/10 hover:text-white'}`}><Icon name="x" size={16}/></button></div></td></tr>)}</tbody></table></div></div><div className={`${THEME.surface} h-fit p-5 md:p-6 sticky top-6`}><h3 className="mb-3 text-lg font-semibold text-white flex items-center gap-2"><Icon name="info" size={18} className="text-white/50"/>Детали</h3>{selected ? <pre className="max-h-[420px] overflow-auto rounded-xl border border-white/10 bg-[#050505] p-4 text-[11px] md:text-xs text-white/50 custom-scrollbar whitespace-pre-wrap word-break shadow-inner page-enter">{JSON.stringify(selected, null, 2)}</pre> : <div className="flex flex-col items-center justify-center py-10 text-center text-sm text-white/40"><Icon name="history" size={32} className="mb-3 opacity-20"/>Выбери команду из истории</div>}</div></div></div>
}

function SettingsPage() {
  const [settings, setSettings] = useState<SettingsPayload>(cloneJson(defaultSettings))
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingMic, setTestingMic] = useState(false)
  const [preloading, setPreloading] = useState(false)
  const [micTranscript, setMicTranscript] = useState('')
  const { showToast } = useToast()

  useEffect(() => {
    let mounted = true
    Promise.all([beavisCall<SettingsPayload>('settings.load'), beavisCall('system.health')]).then(([settingsRes]) => {
      if (!mounted) return
      if (settingsRes.ok && settingsRes.data) setSettings(settingsRes.data)
      setLoading(false)
    })
    return () => { mounted = false }
  }, [])

  const agentNamesText = useMemo(() => settings.voice.agent_names.join('\n'), [settings.voice.agent_names])
  const micOptions = useMemo(() => {
    const base = ['Default Microphone', 'Microphone Array', 'USB Microphone']
    const values = Array.from(new Set([settings.voice.microphone_device || 'Default Microphone', ...base].filter(Boolean)))
    return values.map((value) => ({ value, label: value }))
  }, [settings.voice.microphone_device])
  
  const patch = (next: Partial<SettingsPayload>) => setSettings((prev) => ({ ...prev, ...next }))
  const patchVoice = (next: Partial<SettingsPayload['voice']>) => setSettings((prev) => ({ ...prev, voice: { ...prev.voice, ...next } }))
  const patchStt = (next: Partial<SettingsPayload['voice']['stt']>) => setSettings((prev) => ({ ...prev, voice: { ...prev.voice, stt: { ...prev.voice.stt, ...next } } }))
  const patchVad = (next: Partial<SettingsPayload['voice']['vad']>) => setSettings((prev) => ({ ...prev, voice: { ...prev.voice, vad: { ...prev.voice.vad, ...next } } }))
  
  const save = async () => { setSaving(true); const result = await beavisCall('settings.save', settings as unknown as Record<string, unknown>); setSaving(false); result.ok ? showToast('Настройки сохранены', 'success') : showToast(result.error || 'Ошибка сохранения', 'error') }
  const resetLocal = () => { setSettings(cloneJson(defaultSettings)); setMicTranscript(''); showToast('Настройки сброшены локально', 'info') }
  const testMicrophone = async () => { setTestingMic(true); setMicTranscript(''); const result = await beavisCall<any>('voice.test_microphone'); setTestingMic(false); if (result.ok && result.data) { setMicTranscript(result.data.transcript || 'Речь не распознана'); showToast('Микрофон проверен', 'success') } else showToast(result.error || 'Ошибка микрофона', 'error') }
  const preloadVoice = async () => { setPreloading(true); const result = await beavisCall('voice.preload'); setPreloading(false); result.ok ? showToast('Голосовая модель загружена', 'success') : showToast(result.error || 'Ошибка загрузки модели', 'error') }
  const reloadPipeline = async () => { const result = await beavisCall('commands.reload'); result.ok ? showToast('Pipeline перезагружен', 'success') : showToast(result.error || 'Ошибка reload', 'error') }

  if (loading) return <div className="flex min-h-[70vh] items-center justify-center text-white/40"><Spinner size={24} className="mr-3"/>Загружаю настройки...</div>

  return <div className={THEME.page}><div className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between"><div><h2 className="text-3xl md:text-4xl font-light tracking-tight text-white">Настройки</h2><p className="mt-2 text-sm text-white/40">Хоткеи, голос, STT-модель и чувствительность записи.</p></div><div className="flex flex-wrap items-center gap-3"><button onClick={reloadPipeline} className={`${THEME.ghostBtn} flex items-center gap-2`}><Icon name="refresh" size={17}/><span className="hidden sm:inline">Reload</span></button><button onClick={resetLocal} className={`${THEME.ghostBtn} flex items-center gap-2`}><Icon name="rotate" size={17}/><span className="hidden sm:inline">Сбросить</span></button><button onClick={save} disabled={saving} className={`${THEME.primaryBtn} flex items-center gap-2`}>{saving ? <Spinner size={17}/> : <Icon name="save" size={17}/>}Сохранить</button></div></div><div className="grid grid-cols-1 gap-5 lg:grid-cols-2"><SectionCard icon="keyboard" title="Хоткеи" subtitle="Быстрый ввод команды и голосовой запуск." delayClass="stagger-1"><div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div className="flex min-h-[156px] flex-col justify-between rounded-2xl border border-white/10 bg-[#050505] p-4 transition-all duration-300 hover:border-white/20 hover:shadow-[0_0_20px_rgba(255,255,255,0.03)]"><div className="flex items-start justify-between gap-5"><div><div className="text-sm font-semibold text-white">Текстовый overlay</div><div className="mt-1 text-xs text-white/40">Открывает строку команды</div></div><Toggle checked={settings.text_hotkey_enabled} onChange={(value) => patch({ text_hotkey_enabled: value })}/></div><Field label="Комбинация"><GlassInput value={settings.text_hotkey_sequence} onChange={(e) => patch({ text_hotkey_sequence: e.target.value })} className="font-mono text-center tracking-widest text-white/80"/></Field></div><div className="flex min-h-[156px] flex-col justify-between rounded-2xl border border-white/10 bg-[#050505] p-4 transition-all duration-300 hover:border-white/20 hover:shadow-[0_0_20px_rgba(255,255,255,0.03)]"><div className="flex items-start justify-between gap-5"><div><div className="text-sm font-semibold text-white">Голосовой overlay</div><div className="mt-1 text-xs text-white/40">Запускает запись команды</div></div><Toggle checked={settings.voice.hotkey_enabled} onChange={(value) => patchVoice({ hotkey_enabled: value })}/></div><Field label="Комбинация"><GlassInput value={settings.voice.hotkey_sequence} onChange={(e) => patchVoice({ hotkey_sequence: e.target.value })} className="font-mono text-center tracking-widest text-white/80"/></Field></div></div></SectionCard><SectionCard icon="mic" title="Голосовой режим" subtitle="Как агент слушает и когда требует имя агента." delayClass="stagger-2"><div className="relative grid grid-cols-3 overflow-hidden rounded-2xl border border-white/10 bg-[#050505] p-1.5"><div className="absolute bottom-1.5 top-1.5 rounded-xl bg-white shadow-[0_0_28px_rgba(255,255,255,.35)] transition-all duration-500 ease-out" style={{ left: `calc(${(['off', 'hotkey', 'continuous'].indexOf(settings.voice.mode)) * 33.333333}% + 6px)`, width: 'calc(33.333333% - 12px)' }}/>{[['off', 'Выкл'], ['hotkey', 'Hotkey'], ['continuous', 'Фон']].map(([value, label]) => <button key={value} onClick={() => patchVoice({ mode: value as SettingsPayload['voice']['mode'] })} className={`relative z-10 rounded-xl px-3 py-3 text-sm font-semibold transition-colors duration-300 ${settings.voice.mode === value ? 'text-black' : 'text-white/50 hover:text-white/75'}`}>{label}</button>)}</div><div className="grid grid-cols-1 gap-4 md:grid-cols-2"><Field label="Микрофон"><GlassDropdown value={settings.voice.microphone_device || 'Default Microphone'} onChange={(value) => patchVoice({ microphone_device: value })} options={micOptions}/></Field><Field label="Имена агента" hint="по одному в строке"><textarea rows={2} value={agentNamesText} onChange={(e) => patchVoice({ agent_names: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} className={`${THEME.input} h-[68px] resize-none overflow-hidden leading-6`}/></Field></div><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div className="flex min-h-[86px] items-center justify-between gap-5 rounded-2xl border border-white/10 bg-[#050505] p-4 transition-all hover:border-white/20"><div><div className="text-sm font-semibold text-white">Wake word в фоне</div><div className="mt-1 text-xs text-white/40">Требовать “Бивис”</div></div><Toggle checked={settings.voice.require_wake_word_for_continuous} onChange={(value) => patchVoice({ require_wake_word_for_continuous: value })}/></div><div className="flex min-h-[86px] items-center justify-between gap-5 rounded-2xl border border-white/10 bg-[#050505] p-4 transition-all hover:border-white/20"><div><div className="text-sm font-semibold text-white">Preload на старте</div><div className="mt-1 text-xs text-white/40">Загрузить STT заранее</div></div><Toggle checked={settings.voice.preload_model_on_startup} onChange={(value) => patchVoice({ preload_model_on_startup: value })}/></div></div></SectionCard><SectionCard icon="cpu" title="STT модель" subtitle="Профиль распознавания речи и вычисления." delayClass="stagger-3"><div className="grid grid-cols-1 gap-4 md:grid-cols-2"><Field label="Профиль" info="Готовый набор параметров STT. Turbo — быстрый режим для обычных команд, accuracy — точнее, но тяжелее."><GlassDropdown value={settings.voice.stt.profile} onChange={(value) => patchStt({ profile: value as SettingsPayload['voice']['stt']['profile'] })} options={['auto', 'turbo', 'cpu', 'accuracy', 'custom'].map((value) => ({ value, label: value }))}/></Field><Field label="Модель" info="Размер/тип Whisper-модели. Чем больше модель, тем выше качество и задержка."><GlassDropdown value={settings.voice.stt.model_size} onChange={(value) => patchStt({ model_size: value })} options={['turbo', 'large-v3-turbo', 'small', 'medium', 'base', 'tiny', 'large-v3'].map((value) => ({ value, label: value }))}/></Field><Field label="Device" info="Где считать распознавание: auto выбирает сам, cpu всегда на процессоре, cuda — на видеокарте."><GlassDropdown value={settings.voice.stt.device} onChange={(value) => patchStt({ device: value as SettingsPayload['voice']['stt']['device'] })} options={['auto', 'cpu', 'cuda'].map((value) => ({ value, label: value }))}/></Field><Field label="Compute" info="Формат вычислений. Auto безопаснее всего; float16 обычно для CUDA, int8 легче для CPU."><GlassDropdown value={settings.voice.stt.compute_type} onChange={(value) => patchStt({ compute_type: value as SettingsPayload['voice']['stt']['compute_type'] })} options={['auto', 'int8', 'float16', 'int8_float16', 'float32'].map((value) => ({ value, label: value }))}/></Field></div><div className="flex flex-wrap gap-3 pt-1"><button onClick={preloadVoice} disabled={preloading} className={`${THEME.ghostBtn} flex items-center gap-2`}>{preloading ? <Spinner size={17}/> : <Icon name="radio" size={17}/>}Preload model</button><button onClick={testMicrophone} disabled={testingMic} className={`${THEME.primaryBtn} flex items-center gap-2`}>{testingMic ? <Spinner size={17}/> : <Icon name="mic" size={17}/>}Test microphone</button></div>{micTranscript && <div className="rounded-2xl border border-green-500/20 bg-green-500/[0.08] p-4 text-sm text-green-100 page-enter"><div className="mb-1 text-xs uppercase tracking-[0.18em] text-green-300/70">Transcript</div>{micTranscript}</div>}</SectionCard><SectionCard icon="sliders" title="VAD и тишина" subtitle="Когда остановить запись и насколько чувствительно слушать." delayClass="stagger-4"><Field label="Sensitivity" hint={settings.voice.vad.sensitivity.toFixed(3)} info="Чувствительность к голосу. Выше значение — легче срабатывает на тихий голос, но больше риск шума."><input type="range" min="0.001" max="0.2" step="0.001" value={settings.voice.vad.sensitivity} onChange={(e) => patchVad({ sensitivity: Number(e.target.value) })} className="w-full accent-white cursor-pointer h-2 bg-white/10 rounded-lg appearance-none"/></Field><div className="grid grid-cols-1 items-end gap-3 md:grid-cols-3"><Field label="Hotkey silence (ms)" info="Сколько миллисекунд тишины ждать после голосовой команды, запущенной hotkey."><NumberField value={settings.voice.vad.hotkey_silence_ms} onChange={(value) => patchVad({ hotkey_silence_ms: value })}/></Field><Field label="Continuous silence (ms)" info="Сколько тишины ждать в фоновом режиме перед остановкой текущей фразы."><NumberField value={settings.voice.vad.continuous_silence_ms} onChange={(value) => patchVad({ continuous_silence_ms: value })}/></Field><Field label="Max utterance (ms)" info="Максимальная длина одной голосовой фразы. После этого запись остановится принудительно."><NumberField value={settings.voice.vad.max_utterance_ms} onChange={(value) => patchVad({ max_utterance_ms: value })}/></Field></div></SectionCard></div></div>
}

function CommandOverlay({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()
  useEffect(() => { if (isOpen) setTimeout(() => inputRef.current?.focus(), 50) }, [isOpen])
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (!query.trim()) return; const command = query; setQuery(''); onClose(); const res = await beavisCall('commands.run', { text: command, execute: true, source: 'overlay' }); res.ok ? showToast(`Выполнено: ${command}`, 'success') : showToast(res.error || 'Ошибка', 'error') }
  if (!isOpen) return null
  return <div className="fixed inset-0 z-[500] flex items-center justify-center bg-black/60 px-4 backdrop-blur-xl transition-opacity page-enter" onClick={onClose}><form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="relative w-full max-w-3xl"><div className="relative flex items-center rounded-3xl border border-white/[0.18] bg-[#111] p-3 shadow-[0_40px_100px_rgba(0,0,0,0.8),inset_0_1px_1px_rgba(255,255,255,.12)] transition-all focus-within:shadow-[0_40px_120px_rgba(255,255,255,0.1),inset_0_1px_1px_rgba(255,255,255,.2)] focus-within:border-white/30"><div className="pl-5 pr-2 text-white/50"><Icon name="zap" size={28}/></div><input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && onClose()} placeholder="Что нужно сделать?" className="flex-1 border-none bg-transparent px-3 py-5 text-2xl font-light text-white outline-none placeholder:text-white/25"/><div className="pr-4 hidden sm:block"><span className="rounded border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-white/30 font-mono">ESC to cancel</span></div></div></form></div>
}

function VoiceOverlay({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [status, setStatus] = useState<'idle' | 'listening' | 'processing'>('idle')
  const [transcript, setTranscript] = useState('')
  const { showToast } = useToast()

  // Typewriter effect strictly for the transcript reveal in processing state
  const displayedTranscript = useTypewriter([transcript], 40, 10000); 

  useEffect(() => { if (isOpen) start() }, [isOpen])
  const start = async () => { 
    setStatus('listening'); setTranscript(''); 
    const voice = await beavisCall<any>('voice.listen_once'); 
    if (voice.ok && voice.data?.command_text) { 
       setStatus('processing'); 
       setTranscript(voice.data.command_text); 
       const run = await beavisCall('commands.run', { text: voice.data.command_text, execute: true, source: 'voice', meta: voice.data.meta || {} }); 
       if (run.ok) {
           showToast('Голосовая команда выполнена', 'success');
           setTimeout(() => { onClose(); setStatus('idle') }, 2000) 
       } else {
           showToast(run.error || 'Ошибка', 'error');
           setTimeout(() => { onClose(); setStatus('idle') }, 1500) 
       }
    } else { 
       showToast('Речь не распознана', 'error'); setStatus('idle'); onClose() 
    } 
  }
  
  if (!isOpen) return null
  return <div className="fixed inset-0 z-[500] flex items-center justify-center bg-black/80 backdrop-blur-2xl transition-opacity page-enter" onClick={onClose}><div className="flex flex-col items-center gap-10" onClick={(e) => e.stopPropagation()}><div className="relative flex h-48 w-48 items-center justify-center">{status === 'listening' && <><div className="absolute inset-0 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite] rounded-full border border-white/20 opacity-100"/><div className="absolute inset-4 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite_0.5s] rounded-full bg-white/5 blur-xl"/></>}<div className={`relative flex h-28 w-28 items-center justify-center rounded-full border border-white bg-white/90 text-black shadow-[0_0_55px_rgba(255,255,255,.65)] backdrop-blur-md transition-all duration-500 ${status === 'listening' ? 'scale-110 shadow-[0_0_80px_rgba(255,255,255,.8)]' : ''}`}>{status === 'listening' ? <div className="flex items-center justify-center gap-[3px] h-10 mt-1">{[0, 0.2, 0.4, 0.1, 0.5].map((delay, i) => <div key={i} className="audio-bar" style={{ animationDelay: `${delay}s` }} />)}</div> : status === 'processing' ? <Spinner size={40}/> : <Icon name="mic" size={40}/>}</div></div><div className="text-center"><h3 className="mb-4 text-3xl font-light tracking-wide text-white">{status === 'listening' ? 'Слушаю...' : status === 'processing' ? 'Выполняю...' : 'Готов'}</h3><p className="min-h-[32px] max-w-lg text-xl font-light text-white/40">{status === 'processing' ? displayedTranscript : (status === 'listening' ? 'Говорите команду' : '')}</p></div><button onClick={onClose} className="mt-4 rounded-full border border-white/10 bg-white/5 px-6 py-2 text-sm text-white/40 hover:bg-white/10 hover:text-white transition-colors active:scale-95">Отмена</button></div></div>
}

function AppShell() {
  const [activeTab, setActiveTab] = useState<'home' | 'apps' | 'history' | 'settings'>('home')
  const [isCommandOverlayOpen, setCommandOverlayOpen] = useState(false)
  const [isVoiceOverlayOpen, setVoiceOverlayOpen] = useState(false)
  const [health, setHealth] = useState<'online' | 'offline'>('offline')
  useEffect(() => { runSmokeTests().catch(console.error); beavisCall('system.health').then((result) => setHealth(result.ok ? 'online' : 'offline')); const key = (event: KeyboardEvent) => { if (event.ctrlKey && event.code === 'Space') { event.preventDefault(); setCommandOverlayOpen(true) } if (event.key === 'Escape') { setCommandOverlayOpen(false); setVoiceOverlayOpen(false) } }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key) }, [])
  const nav = [{ id: 'home', label: 'Главная', icon: 'zap' as IconName }, { id: 'apps', label: 'Приложения', icon: 'apps' as IconName }, { id: 'history', label: 'История', icon: 'history' as IconName }, { id: 'settings', label: 'Настройки', icon: 'settings' as IconName }]
  const activeIndex = nav.findIndex((tab) => tab.id === activeTab)
  return <ToastHost><GlobalStyles /><div className={THEME.app}><ParticleStorm/><div className="pointer-events-none fixed left-[-10%] top-[-20%] z-0 h-[120%] w-[120%] bg-[radial-gradient(circle_at_50%_0%,rgba(35,35,42,.42),transparent_58%)] mix-blend-screen"/><div className="pointer-events-none fixed bottom-[-12%] right-[-10%] z-0 h-[60%] w-[60%] rounded-full bg-white/[0.018] blur-[150px] mix-blend-screen"/><header className={THEME.header}><div className="flex items-center gap-6"><button onClick={() => setActiveTab('home')} className="group flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-gradient-to-b from-white to-gray-200 text-lg font-bold text-black shadow-[0_2px_15px_rgba(255,255,255,.3),inset_0_1px_1px_rgba(255,255,255,1)] transition-transform group-hover:scale-105 active:scale-95">B</div><span className="text-xl font-semibold tracking-tight text-white">Beavis</span></button><div className="flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.05] px-3 py-1.5 text-xs text-white/60 backdrop-blur-md shadow-inner"><div className={`h-2 w-2 rounded-full ${health === 'online' ? THEME.greenGlow : THEME.redGlow}`}/>{health === 'online' ? 'Готов' : 'Offline'}</div></div><nav className="absolute left-1/2 top-1/2 hidden w-[520px] -translate-x-1/2 -translate-y-1/2 grid-cols-4 items-center gap-0 rounded-2xl border border-white/[0.07] bg-[#050505]/80 p-1 md:grid shadow-[inset_0_1px_1px_rgba(255,255,255,.05)]"><div className="absolute bottom-1 top-1 rounded-xl bg-white shadow-[0_0_28px_rgba(255,255,255,.35)] transition-all duration-500 ease-out" style={{ left: `calc(${activeIndex * 25}% + 4px)`, width: 'calc(25% - 8px)' }}/>{nav.map((tab) => <button key={tab.id} onClick={() => setActiveTab(tab.id as any)} className={`relative z-10 flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors duration-300 ${activeTab === tab.id ? 'text-black' : 'text-white/50 hover:text-white'}`}><Icon name={tab.icon} size={16}/>{tab.label}</button>)}</nav><div className="flex items-center gap-4 text-white/30"><button className="transition hover:text-white"><span className="block h-px w-3 bg-current"/></button><button className="transition hover:text-white hover:scale-110 active:scale-95"><Icon name="terminal" size={14}/></button><button className="transition hover:text-red-400 hover:scale-110 active:scale-95"><Icon name="x" size={16}/></button></div></header>
  
  <header className={THEME.mobileHeader}><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-white to-gray-300 text-base font-bold text-black shadow-md">B</div><span className="text-lg font-semibold tracking-tight text-white">Beavis</span></div><div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-white/70"><div className={`h-1.5 w-1.5 rounded-full ${health === 'online' ? THEME.greenGlow : THEME.redGlow}`}/>{health === 'online' ? 'Готов' : 'Offline'}</div></header>

  <main className="relative z-10 flex-1 overflow-y-auto overflow-x-hidden pb-24 md:pb-10 custom-scrollbar"><div key={activeTab}>{activeTab === 'home' && <HomePage openVoice={() => setVoiceOverlayOpen(true)}/>} {activeTab === 'apps' && <AppsPage/>} {activeTab === 'history' && <HistoryPage/>} {activeTab === 'settings' && <SettingsPage/>}</div></main>
  
  <div className="fixed bottom-6 left-6 z-40 hidden md:flex gap-3 page-enter stagger-5"><button onClick={() => setCommandOverlayOpen(true)} className="group flex items-center gap-2 rounded-2xl border border-white/10 bg-black/60 px-4 py-2.5 text-sm font-medium text-white/60 shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-xl transition-all duration-300 hover:border-white/30 hover:bg-[#111] hover:text-white active:scale-95 hover:-translate-y-1"><Icon name="keyboard" size={16} className="transition-transform group-hover:scale-110"/> <span className="opacity-60 text-xs">Ctrl+Space</span></button><button onClick={() => setVoiceOverlayOpen(true)} className="group flex items-center gap-2 rounded-2xl border border-white/10 bg-black/60 px-4 py-2.5 text-sm font-medium text-white/60 shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-xl transition-all duration-300 hover:border-white/30 hover:bg-[#111] hover:text-white active:scale-95 hover:-translate-y-1"><Icon name="mic" size={16} className="transition-transform group-hover:scale-110"/> Voice</button></div>

  <nav className="md:hidden fixed bottom-0 left-0 w-full z-40 flex items-center justify-around border-t border-white/10 bg-black/80 pb-safe pt-2 px-2 pb-2 backdrop-blur-2xl">
    {nav.map((tab) => <button key={tab.id} onClick={() => setActiveTab(tab.id as any)} className={`flex flex-col items-center justify-center p-2 rounded-xl min-w-[64px] transition-all duration-300 ${activeTab === tab.id ? 'text-white' : 'text-white/40'}`}><div className={`flex h-8 w-8 items-center justify-center rounded-full transition-all ${activeTab === tab.id ? 'bg-white/15' : ''}`}><Icon name={tab.icon} size={20}/></div><span className="text-[10px] mt-1 font-medium">{tab.label}</span></button>)}
  </nav>

  <CommandOverlay isOpen={isCommandOverlayOpen} onClose={() => setCommandOverlayOpen(false)}/><VoiceOverlay isOpen={isVoiceOverlayOpen} onClose={() => setVoiceOverlayOpen(false)}/></div></ToastHost>
}

export default function App() {
  return <AppShell />
}