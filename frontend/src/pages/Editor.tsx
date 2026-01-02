import { useState, useEffect } from 'react';
import { BotEditor, DEFAULT_BOT_CODE } from '../components/BotEditor';
import { useUsername } from '../hooks/useUsername';
import { getAllUsers, registerUser, deleteUser, getUserBots, getBot, createBot, updateBot, deleteBot, getTemplates, getTemplate, type User, type Bot, type BotListItem, type TemplateInfo } from '../services/botApi';
import { migrateLocalStorageToDatabase } from '../utils/migrateLocalStorage';

export default function Editor() {
  const { username, loading: usernameLoading, promptAndSetUsername, clearUsername } = useUsername();

  const [code, setCode] = useState<string>(DEFAULT_BOT_CODE);
  const [botName, setBotName] = useState<string>('MyBot');
  const [bots, setBots] = useState<BotListItem[]>([]);
  const [currentBot, setCurrentBot] = useState<Bot | null>(null);
  const [saved, setSaved] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [showUserModal, setShowUserModal] = useState<boolean>(false);
  const [availableUsers, setAvailableUsers] = useState<User[]>([]);
  const [newUsername, setNewUsername] = useState<string>('');
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  // Show user selection modal on first visit or if no username
  useEffect(() => {
    if (!usernameLoading && !username) {
      loadAvailableUsers();
      setShowUserModal(true);
    }
  }, [usernameLoading, username]);

  const loadAvailableUsers = async () => {
    try {
      const users = await getAllUsers();
      setAvailableUsers(users);
    } catch (err) {
      console.error('Failed to load users:', err);
      setAvailableUsers([]);
    }
  };

  // Load templates on mount
  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const templateList = await getTemplates();
      setTemplates(templateList);
    } catch (err) {
      console.error('Failed to load templates:', err);
      setTemplates([]);
    }
  };

  // Load bots when username is available
  useEffect(() => {
    if (username) {
      loadUserBots();

      // Run migration once
      migrateLocalStorageToDatabase(username).then((result) => {
        if (result.migrated) {
          console.log(`Migrated bot "${result.botName}" from localStorage`);
          // Reload bots after migration
          loadUserBots();
        }
      }).catch((err) => {
        console.error('Migration failed:', err);
      });
    }
  }, [username]);

  const loadUserBots = async () => {
    if (!username) return;

    try {
      setLoading(true);
      const userBots = await getUserBots(username);
      setBots(userBots);

      // Load the most recent bot if exists
      if (userBots.length > 0 && !currentBot) {
        const botDetails = await getBot(userBots[0].id);
        setCurrentBot(botDetails);
        setCode(botDetails.code);
        setBotName(botDetails.name);
      }
    } catch (err) {
      console.error('Failed to load bots:', err);
      setError(err instanceof Error ? err.message : 'Failed to load bots');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!username) {
      setError('Please set a username first');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      if (currentBot) {
        // Update existing bot
        const updated = await updateBot(currentBot.id, { name: botName, code });
        setCurrentBot(updated);
      } else {
        // Create new bot
        const newBot = await createBot(username, { name: botName, code });
        setCurrentBot(newBot);
        // Reload bots list
        await loadUserBots();
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setLoading(false);
    }
  };

  const handleNewBot = () => {
    if (confirm('Create a new bot? Unsaved changes to the current bot will be lost.')) {
      setCurrentBot(null);
      setCode(DEFAULT_BOT_CODE);
      setBotName('MyBot');
      setSaved(false);
      setError(null);
    }
  };

  const handleDeleteBot = async () => {
    if (!currentBot) return;

    if (confirm(`Delete bot "${currentBot.name}"? This cannot be undone.`)) {
      try {
        setLoading(true);
        await deleteBot(currentBot.id);

        // Clear current bot
        setCurrentBot(null);
        setCode(DEFAULT_BOT_CODE);
        setBotName('MyBot');

        // Reload bots list
        await loadUserBots();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete bot');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleSelectBot = async (botId: number) => {
    try {
      setLoading(true);
      const bot = await getBot(botId);
      setCurrentBot(bot);
      setCode(bot.code);
      setBotName(bot.name);
      setSaved(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load bot');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    if (confirm('Reset to default template? This will discard your current code.')) {
      setCode(DEFAULT_BOT_CODE);
      setBotName(currentBot ? currentBot.name : 'MyBot');
      setSaved(false);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${botName}.py`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result;
      if (typeof text === 'string') {
        setCode(text);
        // Extract bot name from filename
        const name = file.name.replace('.py', '');
        setBotName(name);
      }
    };
    reader.readAsText(file);
  };

  const handleLoadTemplate = async () => {
    if (!selectedTemplate) {
      setError('Please select a template first');
      return;
    }

    const template = templates.find(t => t.id === selectedTemplate);
    if (!template) return;

    // Confirm before overwriting current code
    const confirmMsg = `Load "${template.name}" template? This will replace your current code.`;
    if (!confirm(confirmMsg)) {
      return;
    }

    try {
      setLoading(true);
      const templateData = await getTemplate(selectedTemplate);
      setCode(templateData.code);
      setBotName(template.name);

      // Clear current bot (we're starting fresh with a template)
      setCurrentBot(null);
      setSaved(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load template');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectExistingUser = async (selectedUsername: string) => {
    try {
      setLoading(true);
      // Register user (idempotent - will return existing user)
      const user = await registerUser(selectedUsername);
      localStorage.setItem('coderally_username', user.username);
      setShowUserModal(false);
      window.location.reload(); // Reload to update state
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select user');
      setLoading(false);
    }
  };

  const handleCreateNewUser = async () => {
    if (!newUsername.trim()) {
      setError('Please enter a username');
      return;
    }

    try {
      setLoading(true);
      const user = await registerUser(newUsername.trim());
      localStorage.setItem('coderally_username', user.username);
      setShowUserModal(false);
      setNewUsername('');
      window.location.reload(); // Reload to update state
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userToDelete: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent selecting the user when clicking delete

    if (!confirm(`Delete user "${userToDelete}" and all their bots? This cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      await deleteUser(userToDelete);

      // If we deleted the current user, clear username
      if (userToDelete === username) {
        clearUsername();
      }

      // Reload the user list
      await loadAvailableUsers();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchUser = () => {
    if (confirm('Switch user? You will be logged out and can log in as a different user.')) {
      clearUsername();
      setBots([]);
      setCurrentBot(null);
      setCode(DEFAULT_BOT_CODE);
      setBotName('MyBot');
      setSaved(false);
      setError(null);
      // Show user modal
      loadAvailableUsers();
      setShowUserModal(true);
    }
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-3xl font-bold">Bot Editor</h2>
        {username && (
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-400">
              Logged in as <span className="text-green-400 font-semibold">{username}</span>
            </div>
            <button
              onClick={handleSwitchUser}
              className="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700 transition"
              title="Switch to a different user"
            >
              🔄 Switch User
            </button>
          </div>
        )}
      </div>

      <p className="text-gray-300 mb-6">
        Write your racing bot using Python. Your bot inherits from <code className="bg-gray-700 px-2 py-1 rounded">BaseBot</code> and
        implements <code className="bg-gray-700 px-2 py-1 rounded">on_tick()</code> to control the car.
      </p>

      {/* Bot Management Section */}
      {username && (
        <div className="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
          <div className="flex items-center gap-4 mb-3">
            <label className="text-sm font-semibold">My Bots</label>
            <button
              onClick={handleNewBot}
              className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              ➕ New Bot
            </button>
            {currentBot && (
              <button
                onClick={handleDeleteBot}
                className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={loading}
              >
                🗑️ Delete Bot
              </button>
            )}
          </div>

          {bots.length > 0 ? (
            <select
              value={currentBot?.id || ''}
              onChange={(e) => handleSelectBot(Number(e.target.value))}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              {!currentBot && <option value="">-- Select a bot --</option>}
              {bots.map((bot) => (
                <option key={bot.id} value={bot.id}>
                  {bot.name} (updated {new Date(bot.updated_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm text-gray-400 italic">
              No bots yet. Click "New Bot" to create your first bot!
            </p>
          )}
        </div>
      )}

      {/* Template Selection Section */}
      <div className="mb-6 p-4 bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-lg border border-purple-700/50">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">📚</span>
          <label className="text-sm font-semibold text-purple-200">Start from a Template</label>
        </div>

        <p className="text-sm text-gray-300 mb-3">
          Load a pre-built bot template to learn different racing strategies. Great for beginners!
        </p>

        <div className="flex gap-3 flex-wrap items-start">
          <div className="flex-1 min-w-[200px]">
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              <option value="">-- Select a template --</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {'★'.repeat(template.difficulty)}{'☆'.repeat(5 - template.difficulty)} {template.name}
                </option>
              ))}
            </select>

            {selectedTemplate && templates.find(t => t.id === selectedTemplate) && (
              <div className="mt-2 p-3 bg-gray-800/50 rounded border border-gray-700">
                <p className="text-sm text-gray-300 mb-2">
                  {templates.find(t => t.id === selectedTemplate)?.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {templates.find(t => t.id === selectedTemplate)?.features.map((feature, idx) => (
                    <span key={idx} className="text-xs px-2 py-1 bg-purple-600/30 text-purple-200 rounded">
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleLoadTemplate}
            className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading || !selectedTemplate}
          >
            📥 Load Template
          </button>
        </div>
      </div>

      {/* Bot Name Input */}
      <div className="mb-4">
        <label className="block text-sm font-semibold mb-2">Bot Name</label>
        <input
          type="text"
          value={botName}
          onChange={(e) => setBotName(e.target.value)}
          className="px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white w-full max-w-md disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="MyBot"
          disabled={loading || !username}
        />
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex gap-3 flex-wrap items-center">
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={loading || !username}
        >
          💾 {currentBot ? 'Update Bot' : 'Save New Bot'}
        </button>

        <button
          onClick={handleDownload}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition disabled:opacity-50"
          disabled={loading}
        >
          ⬇️ Download .py
        </button>

        <label className={`px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition cursor-pointer ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
          ⬆️ Upload .py
          <input
            type="file"
            accept=".py"
            onChange={handleFileUpload}
            className="hidden"
            disabled={loading}
          />
        </label>

        <button
          onClick={handleReset}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={loading}
        >
          🔄 Reset Code
        </button>

        {saved && (
          <span className="px-3 py-1 bg-green-900/50 text-green-400 rounded border border-green-600">
            ✓ Saved!
          </span>
        )}

        {error && (
          <span className="px-3 py-1 bg-red-900/50 text-red-400 rounded border border-red-600">
            ✗ {error}
          </span>
        )}

        {loading && (
          <span className="px-3 py-1 bg-blue-900/50 text-blue-400 rounded border border-blue-600">
            ⏳ Loading...
          </span>
        )}
      </div>

      {/* Editor */}
      <div className="mb-6">
        <BotEditor
          value={code}
          onChange={setCode}
          height="600px"
        />
      </div>

      {/* Help Section */}
      <div className="bg-gray-800 p-6 rounded-lg">
        <h3 className="text-xl font-semibold mb-3">Bot API Reference</h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-semibold text-green-400 mb-2">Available Methods</h4>
            <ul className="text-sm text-gray-300 space-y-2">
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">on_tick(state)</code>
                <p className="text-gray-400 ml-2">Called every ~50ms. Return BotActions.</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">on_checkpoint(index, time)</code>
                <p className="text-gray-400 ml-2">Called when passing checkpoints.</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">on_finish(time, position)</code>
                <p className="text-gray-400 ml-2">Called when finishing the race.</p>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-blue-400 mb-2">BotGameState</h4>
            <ul className="text-sm text-gray-300 space-y-2">
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">state.car</code>
                <p className="text-gray-400 ml-2">position, speed, heading, nitro_charges</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">state.rays</code>
                <p className="text-gray-400 ml-2">7 raycasts: [0]=forward, [1-3]=right, [4-6]=left</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">state.track</code>
                <p className="text-gray-400 ml-2">checkpoints, next_checkpoint</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">state.opponents</code>
                <p className="text-gray-400 ml-2">Visible nearby cars</p>
              </li>
              <li>
                <code className="bg-gray-700 px-2 py-1 rounded">state.race</code>
                <p className="text-gray-400 ml-2">current_checkpoint, position, elapsed_time</p>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6">
          <h4 className="font-semibold text-purple-400 mb-2">BotActions</h4>
          <p className="text-sm text-gray-300">
            Return <code className="bg-gray-700 px-2 py-1 rounded">BotActions(accelerate=True, brake=False, turn_left=False, turn_right=False, use_nitro=False)</code>
          </p>
        </div>

        <div className="mt-6">
          <h4 className="font-semibold text-yellow-400 mb-2">Memory (Persistent Storage)</h4>
          <p className="text-sm text-gray-300">
            Use <code className="bg-gray-700 px-2 py-1 rounded">self.memory</code> dict to save data between races.
            Perfect for learning algorithms and tracking statistics.
          </p>
        </div>

        <div className="mt-6 p-4 bg-gray-900 rounded border border-gray-700">
          <p className="text-sm text-gray-400">
            <strong>Note:</strong> Bots run in a secure sandbox with limited access.
            Only the <code className="bg-gray-700 px-1 rounded">math</code> module is available for imports.
            No file I/O, network access, or dangerous operations allowed.
          </p>
        </div>
      </div>

      {/* Next Steps */}
      <div className="mt-6 p-4 bg-blue-900/20 border border-blue-600 rounded">
        <h4 className="font-semibold text-blue-400 mb-2">Next Steps</h4>
        <p className="text-sm text-gray-300">
          Once you've written your bot, save it and head to the{' '}
          <strong>Multiplayer</strong> page to test it in a race!
          (Bot submission API integration coming soon)
        </p>
      </div>

      {/* User Selection Modal */}
      {showUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 border border-gray-600">
            <h3 className="text-2xl font-bold mb-4">Select or Create User</h3>

            {availableUsers.length > 0 && (
              <div className="mb-6">
                <h4 className="text-sm font-semibold mb-2 text-gray-300">Existing Users</h4>
                <div className="max-h-48 overflow-y-auto bg-gray-900 rounded border border-gray-700">
                  {availableUsers.map((user) => (
                    <div
                      key={user.id}
                      className="flex items-center justify-between px-4 py-3 hover:bg-gray-700 transition border-b border-gray-700 last:border-b-0"
                    >
                      <button
                        onClick={() => handleSelectExistingUser(user.username)}
                        className="flex-1 text-left"
                        disabled={loading}
                      >
                        <div className="font-semibold text-white">{user.username}</div>
                        <div className="text-xs text-gray-400">
                          Created {new Date(user.created_at).toLocaleDateString()}
                        </div>
                      </button>
                      <button
                        onClick={(e) => handleDeleteUser(user.username, e)}
                        className="ml-3 px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition disabled:opacity-50"
                        disabled={loading}
                        title="Delete this user and all their bots"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mb-4">
              <h4 className="text-sm font-semibold mb-2 text-gray-300">Create New User</h4>
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateNewUser()}
                placeholder="Enter new username (3-50 chars)"
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white disabled:opacity-50"
                disabled={loading}
              />
              <p className="text-xs text-gray-400 mt-1">
                Letters, numbers, dashes, and underscores only
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleCreateNewUser}
                className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={loading || !newUsername.trim()}
              >
                ➕ Create User
              </button>
            </div>

            {error && (
              <div className="mt-4 px-3 py-2 bg-red-900/50 text-red-400 rounded border border-red-600 text-sm">
                {error}
              </div>
            )}

            {loading && (
              <div className="mt-4 text-center text-gray-400 text-sm">
                ⏳ Loading...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
