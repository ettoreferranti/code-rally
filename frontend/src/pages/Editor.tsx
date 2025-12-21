import { useState, useEffect } from 'react';
import { BotEditor, DEFAULT_BOT_CODE } from '../components/BotEditor';

export default function Editor() {
  const [code, setCode] = useState<string>(DEFAULT_BOT_CODE);
  const [botName, setBotName] = useState<string>('MyBot');
  const [saved, setSaved] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load saved code from localStorage on mount
  useEffect(() => {
    const savedCode = localStorage.getItem('bot_code');
    const savedName = localStorage.getItem('bot_name');

    if (savedCode) {
      setCode(savedCode);
    }
    if (savedName) {
      setBotName(savedName);
    }
  }, []);

  const handleSave = () => {
    try {
      // Save to localStorage
      localStorage.setItem('bot_code', code);
      localStorage.setItem('bot_name', botName);

      setSaved(true);
      setError(null);

      // Clear saved indicator after 2 seconds
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    }
  };

  const handleReset = () => {
    if (confirm('Reset to default template? This will discard your current code.')) {
      setCode(DEFAULT_BOT_CODE);
      setBotName('MyBot');
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

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Bot Editor</h2>

      <p className="text-gray-300 mb-6">
        Write your racing bot using Python. Your bot inherits from <code className="bg-gray-700 px-2 py-1 rounded">BaseBot</code> and
        implements <code className="bg-gray-700 px-2 py-1 rounded">on_tick()</code> to control the car.
      </p>

      {/* Bot Name Input */}
      <div className="mb-4">
        <label className="block text-sm font-semibold mb-2">Bot Name</label>
        <input
          type="text"
          value={botName}
          onChange={(e) => setBotName(e.target.value)}
          className="px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white w-full max-w-md"
          placeholder="MyBot"
        />
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex gap-3 flex-wrap items-center">
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
        >
          💾 Save to Browser
        </button>

        <button
          onClick={handleDownload}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
        >
          ⬇️ Download .py
        </button>

        <label className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition cursor-pointer">
          ⬆️ Upload .py
          <input
            type="file"
            accept=".py"
            onChange={handleFileUpload}
            className="hidden"
          />
        </label>

        <button
          onClick={handleReset}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition"
        >
          🔄 Reset to Template
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
    </div>
  );
}
