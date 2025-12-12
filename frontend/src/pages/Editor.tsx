export default function Editor() {
  return (
    <div className="p-8">
      <h2 className="text-3xl font-bold mb-4">Bot Editor</h2>
      <p className="text-gray-300 mb-4">
        Write your bot code here using Monaco Editor
      </p>
      <div className="bg-gray-800 p-4 rounded-lg">
        <div className="bg-gray-900 rounded h-96 flex items-center justify-center">
          <p className="text-gray-500">Monaco Editor Placeholder</p>
        </div>
      </div>
    </div>
  )
}
