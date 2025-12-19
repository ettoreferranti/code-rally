import { Link, Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="flex flex-col min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gradient-to-br from-purple-600 to-purple-800 text-white py-6 px-4">
        <div className="container mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold">CodeRally</h1>
              <p className="text-sm opacity-90">
                Top-down 2D racing game with programmable bots
              </p>
            </div>
            <nav className="flex gap-4">
              <Link
                to="/"
                className="px-4 py-2 rounded hover:bg-white/20 transition"
              >
                Home
              </Link>
              <Link
                to="/practice"
                className="px-4 py-2 rounded hover:bg-white/20 transition"
              >
                Practice
              </Link>
              <Link
                to="/multiplayer"
                className="px-4 py-2 rounded hover:bg-white/20 transition"
              >
                Multiplayer
              </Link>
              <Link
                to="/editor"
                className="px-4 py-2 rounded hover:bg-white/20 transition"
              >
                Editor
              </Link>
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <div className="container mx-auto">
          <Outlet />
        </div>
      </main>
      <footer className="bg-gray-800 py-4 px-4 text-center text-sm text-gray-400">
        <p>Built with React + Vite + Tailwind CSS</p>
      </footer>
    </div>
  )
}
