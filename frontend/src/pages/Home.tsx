export default function Home() {
  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Welcome to CodeRally</h2>
      <p className="text-lg text-gray-300 mb-4">
        Race using keyboard controls or write Python bots to compete
        autonomously.
      </p>
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
