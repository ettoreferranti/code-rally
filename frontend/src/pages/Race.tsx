export default function Race() {
  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Race</h2>
      <p className="text-gray-300">Game canvas will be rendered here</p>
      <div className="mt-8 bg-gray-800 p-4 rounded-lg">
        <div className="aspect-video bg-gray-900 rounded flex items-center justify-center">
          <p className="text-gray-500">Game Canvas Placeholder</p>
        </div>
      </div>
    </div>
  )
}
