import { useNavigate } from 'react-router-dom';

/**
 * Landing page with two big choices: PLAY (jump into lobbies) or
 * TINKER WITH BOTS (manage the bot library). All other entry points
 * (Practice, Quick-play Multiplayer) collapse into "create a lobby".
 */
export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-10 text-center">
          <h2 className="text-4xl font-bold mb-3">Welcome to CodeRally</h2>
          <p className="text-lg text-gray-400">
            Race a top-down 2D rally car — by hand, with a Python bot you wrote, or against a local LLM.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <button
            data-testid="tile-play"
            onClick={() => navigate('/lobbies')}
            className="
              group relative overflow-hidden text-left rounded-2xl
              bg-gradient-to-br from-green-700/80 to-green-900/80
              border border-green-600/40 hover:border-green-400/60
              p-8 h-64 transition transform hover:-translate-y-0.5
              shadow-lg hover:shadow-green-900/40
            "
          >
            <div className="text-6xl mb-4 transition group-hover:scale-110 inline-block">🏁</div>
            <div className="text-3xl font-bold mb-2">Play</div>
            <p className="text-green-100/90 text-sm leading-snug">
              Join an existing lobby or create your own. Race solo, against humans, or against bots from your library.
            </p>
          </button>

          <button
            data-testid="tile-tinker"
            onClick={() => navigate('/tinker')}
            className="
              group relative overflow-hidden text-left rounded-2xl
              bg-gradient-to-br from-purple-700/80 to-purple-900/80
              border border-purple-600/40 hover:border-purple-400/60
              p-8 h-64 transition transform hover:-translate-y-0.5
              shadow-lg hover:shadow-purple-900/40
            "
          >
            <div className="text-6xl mb-4 transition group-hover:scale-110 inline-block">🛠️</div>
            <div className="text-3xl font-bold mb-2">Tinker with bots</div>
            <p className="text-purple-100/90 text-sm leading-snug">
              Build your bot library — code Python drivers or configure local-LLM agents with custom system prompts.
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
