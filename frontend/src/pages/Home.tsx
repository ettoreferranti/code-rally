import { useNavigate } from 'react-router-dom'

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Welcome to CodeRally</h2>
      <p className="text-lg text-gray-300 mb-4">
        Race using keyboard controls or write Python bots to compete
        autonomously.
      </p>

      {/* Action Buttons */}
      <div className="flex gap-4 mt-8 mb-8">
        <button
          onClick={() => navigate('/lobbies')}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-lg font-semibold"
        >
          Browse Lobbies
        </button>
        <button
          onClick={() => navigate('/multiplayer')}
          className="px-6 py-3 bg-green-600 hover:bg-green-500 rounded-lg text-lg font-semibold"
        >
          Quick Play
        </button>
        <button
          onClick={() => navigate('/editor')}
          className="px-6 py-3 bg-purple-600 hover:bg-purple-500 rounded-lg text-lg font-semibold"
        >
          Bot Editor
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
        <div className="bg-gray-800 p-6 rounded-lg">
          <h3 className="text-xl font-bold mb-2">Play Mode</h3>
          <p className="text-gray-400">
            Race manually using keyboard controls
          </p>
        </div>
        <div className="bg-gray-800 p-6 rounded-lg">
          <h3 className="text-xl font-bold mb-2">Bot Mode</h3>
          <p className="text-gray-400">
            Program your own racing bot in Python
          </p>
        </div>
      </div>
    </div>
  )
}
