/**
 * Tinker page — the user's bot library.
 *
 * Replaces the old /editor page. Unified for both bot kinds:
 *   - Python bots: name + Monaco code editor.
 *   - LLM bots: name + model preset dropdown + system_prompt textarea.
 *
 * Layout: bot list on the left (kind badges per row), kind-specific
 * editor on the right. "New bot" opens a small picker (Python | LLM)
 * then the appropriate creation form.
 */

import { useEffect, useState } from 'react';
import { BotEditor, DEFAULT_BOT_CODE } from '../components/BotEditor';
import { useUserSwitcher } from '../components/UserSwitcherProvider';
import { useUsername } from '../hooks/useUsername';
import {
  getUserBots,
  getBot,
  createBot,
  updateBot,
  deleteBot,
  getTemplates,
  getTemplate,
  getLlmModelPresets,
  type Bot,
  type BotListItem,
  type ModelPreset,
  type TemplateInfo,
} from '../services/botApi';

type AddDialog = null | 'choose' | 'python' | 'llm';

const DEFAULT_LLM_SYSTEM_PROMPT = (
  // Pre-filled into the system-prompt textarea for new LLM bots so users
  // can tweak rather than start from scratch. Mirrors the backend default
  // (DEFAULT_SYSTEM_PROMPT in app/agents/llm_strategist.py).
  'You are a rally driver racing to finish the stage AS FAST AS POSSIBLE. ' +
  'Top speed is around 180 km/h. Wet, gravel, and ice surfaces reduce ' +
  "grip but you still race — pick a safer speed and a wider racing line, " +
  'but never stop.\n\n' +
  'Given the observation, decide your driving intent for the next second.\n\n' +
  'Output ONLY a JSON object with these fields:\n' +
  '  "target_speed_kmh": number between 40 and 200\n' +
  '     (40-70 on tight corners or low-grip surfaces; 80-130 on flowing\n' +
  '     corners; 130-180 on straights. NEVER output less than 40.)\n' +
  '  "racing_line_offset_m": number between -10 and 10 (negative = left of centre)\n' +
  '  "aggression": number between 0.3 and 1.0 ' +
  '(0.3 = careful, 1.0 = full attack; use 0.5+ on most segments)\n\n' +
  'Output nothing else. No prose, no markdown, no code fences.'
);

export default function Tinker() {
  const { username, loading: usernameLoading } = useUsername();
  const { openModal: openUserModal } = useUserSwitcher();

  // Library state
  const [bots, setBots] = useState<BotListItem[]>([]);
  const [currentBot, setCurrentBot] = useState<Bot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Python-bot editor state (used when currentBot.kind === 'python')
  const [code, setCode] = useState<string>(DEFAULT_BOT_CODE);

  // LLM-bot form state (used when currentBot.kind === 'llm')
  const [modelPath, setModelPath] = useState<string>('');
  const [systemPrompt, setSystemPrompt] = useState<string>('');

  // Add-bot wizard
  const [addDialog, setAddDialog] = useState<AddDialog>(null);
  const [newName, setNewName] = useState('');
  const [pythonTemplates, setPythonTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  // Template code is fetched on Load and held here until Create or Cancel.
  const [loadedTemplate, setLoadedTemplate] = useState<{ name: string; code: string } | null>(null);
  const [modelPresets, setModelPresets] = useState<ModelPreset[]>([]);
  const [newLlmModel, setNewLlmModel] = useState('');
  const [newLlmCustomMode, setNewLlmCustomMode] = useState(false);
  const [newLlmSystemPrompt, setNewLlmSystemPrompt] = useState(DEFAULT_LLM_SYSTEM_PROMPT);

  // If we landed without a user, defer to the global UserSwitcher.
  useEffect(() => {
    if (!usernameLoading && !username) {
      openUserModal();
    }
  }, [usernameLoading, username, openUserModal]);

  // Load library + presets on user available.
  useEffect(() => {
    if (!username) return;
    let cancelled = false;
    (async () => {
      try {
        const [list, templates, presets] = await Promise.all([
          getUserBots(username),
          getTemplates(),
          getLlmModelPresets().catch(() => [] as ModelPreset[]),  // optional
        ]);
        if (cancelled) return;
        setBots(list);
        setPythonTemplates(templates);
        setModelPresets(presets);
        // Pre-pick the default preset for the LLM creation form.
        const defaultPreset = presets.find((p) => p.default) ?? presets[0];
        if (defaultPreset) setNewLlmModel(defaultPreset.model_path);
      } catch (err) {
        console.error(err);
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load library');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [username]);

  const handleSelectBot = async (botId: number) => {
    setError(null);
    setSaved(false);
    setLoading(true);
    try {
      const bot = await getBot(botId);
      setCurrentBot(bot);
      if (bot.kind === 'python') {
        setCode(bot.code);
      } else {
        setModelPath(bot.model_path ?? '');
        setSystemPrompt(bot.system_prompt ?? '');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load bot');
    } finally {
      setLoading(false);
    }
  };

  const refreshBotList = async () => {
    if (!username) return;
    const list = await getUserBots(username);
    setBots(list);
  };

  const handleSavePython = async () => {
    if (!currentBot) return;
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateBot(currentBot.id, { code });
      setCurrentBot(updated);
      setSaved(true);
      await refreshBotList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save bot');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveLlm = async () => {
    if (!currentBot) return;
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateBot(currentBot.id, {
        model_path: modelPath,
        system_prompt: systemPrompt,
      });
      setCurrentBot(updated);
      setSaved(true);
      await refreshBotList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save bot');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!currentBot) return;
    if (!confirm(`Delete bot "${currentBot.name}"? This cannot be undone.`)) return;
    setLoading(true);
    setError(null);
    try {
      await deleteBot(currentBot.id);
      setCurrentBot(null);
      await refreshBotList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete bot');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadTemplate = async () => {
    if (!selectedTemplate) return;
    setError(null);
    try {
      const tpl = await getTemplate(selectedTemplate);
      setLoadedTemplate({ name: tpl.name, code: tpl.code });
      // Suggest the template's name as the bot name, but don't override
      // what the user has typed.
      if (!newName.trim()) setNewName(tpl.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load template');
    }
  };

  const handleCreatePython = async () => {
    if (!username) return;
    if (!newName.trim()) {
      setError('Bot name is required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const bot = await createBot(username, {
        name: newName.trim(),
        kind: 'python',
        code: loadedTemplate?.code ?? DEFAULT_BOT_CODE,
      });
      setAddDialog(null);
      setNewName('');
      setSelectedTemplate('');
      setLoadedTemplate(null);
      await refreshBotList();
      await handleSelectBot(bot.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create bot');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLlm = async () => {
    if (!username) return;
    if (!newName.trim()) {
      setError('Bot name is required');
      return;
    }
    if (!newLlmModel.trim()) {
      setError('Model path is required');
      return;
    }
    if (!newLlmSystemPrompt.trim()) {
      setError('System prompt is required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const bot = await createBot(username, {
        name: newName.trim(),
        kind: 'llm',
        model_path: newLlmModel.trim(),
        system_prompt: newLlmSystemPrompt,
      });
      setAddDialog(null);
      setNewName('');
      setNewLlmCustomMode(false);
      setNewLlmSystemPrompt(DEFAULT_LLM_SYSTEM_PROMPT);
      const defaultPreset = modelPresets.find((p) => p.default) ?? modelPresets[0];
      if (defaultPreset) setNewLlmModel(defaultPreset.model_path);
      await refreshBotList();
      await handleSelectBot(bot.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create bot');
    } finally {
      setLoading(false);
    }
  };

  if (!username) {
    return (
      <div className="p-8 text-center text-gray-400">
        {usernameLoading ? 'Loading user…' : 'Sign in to manage your bots.'}
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-3xl font-bold">Tinker with bots</h2>
        <button
          onClick={() => { setError(null); setAddDialog('choose'); }}
          className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded font-semibold"
          data-testid="new-bot-button"
        >
          ➕ New bot
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/40 border border-red-700 rounded text-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[20rem,1fr] gap-6">
        {/* Bot library list */}
        <aside className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-gray-700 text-sm text-gray-400 uppercase tracking-wide">
            My bots ({bots.length})
          </div>
          {bots.length === 0 ? (
            <div className="p-4 text-sm text-gray-400 italic">
              No bots yet. Click <strong>New bot</strong> above to create your first one.
            </div>
          ) : (
            <ul className="divide-y divide-gray-700" data-testid="bot-list">
              {bots.map((bot) => {
                const isSelected = currentBot?.id === bot.id;
                return (
                  <li key={bot.id}>
                    <button
                      onClick={() => handleSelectBot(bot.id)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition flex items-center justify-between gap-2 ${
                        isSelected ? 'bg-gray-700' : ''
                      }`}
                      data-testid={`bot-row-${bot.id}`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold truncate">{bot.name}</div>
                        <div className="text-xs text-gray-400 truncate">
                          {bot.kind === 'llm' && bot.model_path
                            ? bot.model_path.replace(/^mlx-community\//, '')
                            : new Date(bot.updated_at).toLocaleDateString()}
                        </div>
                      </div>
                      <span
                        className={`px-2 py-0.5 text-xs rounded font-mono ${
                          bot.kind === 'llm'
                            ? 'bg-purple-700 text-purple-100'
                            : 'bg-blue-700 text-blue-100'
                        }`}
                      >
                        {bot.kind === 'llm' ? 'LLM' : 'PY'}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        {/* Editor / form for the selected bot */}
        <section className="bg-gray-800 border border-gray-700 rounded-lg p-4 min-h-[24rem]">
          {!currentBot ? (
            <div className="h-full flex items-center justify-center text-gray-400">
              Select a bot from the list to edit it, or create a new one.
            </div>
          ) : currentBot.kind === 'python' ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xl font-semibold">{currentBot.name}</div>
                  <div className="text-xs text-gray-400">Python bot · BaseBot subclass</div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleSavePython}
                    disabled={loading}
                    className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm font-semibold disabled:opacity-50"
                  >
                    💾 Save
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={loading}
                    className="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-sm font-semibold disabled:opacity-50"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
              {saved && (
                <div className="px-3 py-1 bg-green-900/40 border border-green-700 rounded text-sm text-green-200">
                  Saved.
                </div>
              )}
              <BotEditor code={code} onChange={setCode} />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xl font-semibold">{currentBot.name}</div>
                  <div className="text-xs text-purple-300">LLM bot · strategist-driven</div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveLlm}
                    disabled={loading}
                    className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm font-semibold disabled:opacity-50"
                  >
                    💾 Save
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={loading}
                    className="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-sm font-semibold disabled:opacity-50"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
              {saved && (
                <div className="px-3 py-1 bg-green-900/40 border border-green-700 rounded text-sm text-green-200">
                  Saved.
                </div>
              )}
              <div>
                <label className="block text-sm font-semibold mb-1">Model</label>
                <input
                  type="text"
                  value={modelPath}
                  onChange={(e) => setModelPath(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm font-mono"
                  data-testid="llm-edit-model"
                />
                <p className="mt-1 text-xs text-gray-400">
                  HuggingFace path (e.g. <code>mlx-community/Qwen2.5-1.5B-Instruct-4bit</code>) or local path.
                </p>
              </div>
              <div>
                <label className="block text-sm font-semibold mb-1">System prompt</label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={12}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-xs font-mono"
                  data-testid="llm-edit-prompt"
                />
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Add-bot wizard */}
      {addDialog && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-2xl p-6">
            {addDialog === 'choose' && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold">What kind of bot?</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    onClick={() => setAddDialog('python')}
                    className="p-4 bg-blue-900/40 border border-blue-700 hover:bg-blue-900/60 rounded text-left"
                    data-testid="new-bot-python"
                  >
                    <div className="font-bold text-lg">Python bot</div>
                    <div className="text-sm text-gray-300">
                      Write code in a sandboxed Python editor. Full control over driving logic.
                    </div>
                  </button>
                  <button
                    onClick={() => setAddDialog('llm')}
                    className="p-4 bg-purple-900/40 border border-purple-700 hover:bg-purple-900/60 rounded text-left"
                    data-testid="new-bot-llm"
                  >
                    <div className="font-bold text-lg">LLM bot</div>
                    <div className="text-sm text-gray-300">
                      Drive via a local language model with a custom system prompt. Research playground.
                    </div>
                  </button>
                </div>
                <div className="flex justify-end">
                  <button onClick={() => setAddDialog(null)} className="px-3 py-1 text-gray-400 hover:text-white text-sm">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {addDialog === 'python' && (
              <div className="space-y-3">
                <h3 className="text-xl font-bold">New Python bot</h3>
                <div>
                  <label className="block text-sm font-semibold mb-1">Name</label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. SpeedBot"
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded"
                    data-testid="new-python-name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-1">Start from template (optional)</label>
                  <div className="flex gap-2">
                    <select
                      value={selectedTemplate}
                      onChange={(e) => {
                        setSelectedTemplate(e.target.value);
                        // A new template choice invalidates a previously-
                        // loaded one until the user clicks Load again.
                        if (loadedTemplate) setLoadedTemplate(null);
                      }}
                      className="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm"
                    >
                      <option value="">— blank —</option>
                      {pythonTemplates.map((t) => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                    <button
                      onClick={handleLoadTemplate}
                      disabled={!selectedTemplate || loadedTemplate?.name === pythonTemplates.find((t) => t.id === selectedTemplate)?.name}
                      className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50"
                    >
                      Load
                    </button>
                  </div>
                  {loadedTemplate ? (
                    <p className="mt-2 text-xs text-green-300">
                      ✓ Loaded <strong>{loadedTemplate.name}</strong> ({loadedTemplate.code.length} chars). It will be saved as the bot's starting code.
                    </p>
                  ) : (
                    <p className="mt-2 text-xs text-gray-500">
                      Pick a template and click Load. The bot will be created with that template's code; you can edit it after.
                    </p>
                  )}
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={() => {
                      setAddDialog(null);
                      setSelectedTemplate('');
                      setLoadedTemplate(null);
                    }}
                    className="px-3 py-1 text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreatePython}
                    disabled={loading || !newName.trim()}
                    className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded font-semibold disabled:opacity-50"
                    data-testid="new-python-submit"
                  >
                    Create
                  </button>
                </div>
              </div>
            )}

            {addDialog === 'llm' && (
              <div className="space-y-3">
                <h3 className="text-xl font-bold">New LLM bot</h3>
                <div>
                  <label className="block text-sm font-semibold mb-1">Name</label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. AggressiveQwen"
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded"
                    data-testid="new-llm-name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-1">Model</label>
                  {!newLlmCustomMode ? (
                    <select
                      value={newLlmModel}
                      onChange={(e) => {
                        if (e.target.value === '__custom__') {
                          setNewLlmCustomMode(true);
                          setNewLlmModel('');
                        } else {
                          setNewLlmModel(e.target.value);
                        }
                      }}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm"
                      data-testid="new-llm-model-preset"
                    >
                      {modelPresets.map((p) => (
                        <option key={p.model_path} value={p.model_path}>
                          {p.label}
                        </option>
                      ))}
                      <option value="__custom__">Custom path…</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={newLlmModel}
                      onChange={(e) => setNewLlmModel(e.target.value)}
                      placeholder="mlx-community/Your-Model-4bit"
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm font-mono"
                      data-testid="new-llm-model-custom"
                    />
                  )}
                  {modelPresets.find((p) => p.model_path === newLlmModel)?.description && (
                    <p className="mt-1 text-xs text-gray-400">
                      {modelPresets.find((p) => p.model_path === newLlmModel)!.description}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-1">
                    System prompt
                    <button
                      type="button"
                      onClick={() => setNewLlmSystemPrompt(DEFAULT_LLM_SYSTEM_PROMPT)}
                      className="ml-2 text-xs text-blue-400 hover:text-blue-300 font-normal"
                    >
                      reset to default
                    </button>
                  </label>
                  <textarea
                    value={newLlmSystemPrompt}
                    onChange={(e) => setNewLlmSystemPrompt(e.target.value)}
                    rows={10}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-xs font-mono"
                    data-testid="new-llm-prompt"
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    The strategist sees this on every tick. Keep the JSON-output instructions intact.
                  </p>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button onClick={() => setAddDialog(null)} className="px-3 py-1 text-gray-400 hover:text-white">Cancel</button>
                  <button
                    onClick={handleCreateLlm}
                    disabled={loading || !newName.trim() || !newLlmModel.trim()}
                    className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded font-semibold disabled:opacity-50"
                    data-testid="new-llm-submit"
                  >
                    Create
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
