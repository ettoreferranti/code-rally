/**
 * Bot code editor using Monaco Editor.
 *
 * Provides a Python code editor with syntax highlighting and autocomplete
 * for the bot API (BaseBot, BotActions, etc.).
 */

import React, { useRef } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';

interface BotEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

// Default bot template
export const DEFAULT_BOT_CODE = `class MyBot(BaseBot):
    """
    My custom racing bot.

    Available in on_tick(state):
    - state.car: position, heading, speed, velocity, nitro_charges, etc.
    - state.rays: 7 raycasts for vision (forward, left, right)
    - state.track: checkpoints, next_checkpoint
    - state.opponents: visible opponent cars (fog of war)
    - state.race: current_checkpoint, position, elapsed_time

    Available actions:
    - accelerate, brake, turn_left, turn_right, use_nitro
    """

    def on_tick(self, state):
        """Called every tick (~20Hz) - return your actions."""
        # Check forward raycast
        front_ray = state.rays[0]

        # Simple obstacle avoidance
        if front_ray.distance < 80:
            return BotActions(
                accelerate=True,
                turn_left=True,
                brake=True
            )

        # Otherwise accelerate
        return BotActions(accelerate=True)

    def on_checkpoint(self, checkpoint_index, split_time):
        """Called when passing a checkpoint."""
        # Track progress in memory
        if 'checkpoints_passed' not in self.memory:
            self.memory['checkpoints_passed'] = 0
        self.memory['checkpoints_passed'] += 1

    def on_finish(self, finish_time, final_position):
        """Called when finishing the race."""
        # Save best time
        if 'best_time' not in self.memory:
            self.memory['best_time'] = finish_time
        elif finish_time < self.memory['best_time']:
            self.memory['best_time'] = finish_time
`;

export const BotEditor: React.FC<BotEditorProps> = ({
  value,
  onChange,
  height = '600px',
  readOnly = false
}) => {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    if (!editor || !monaco) return;
    editorRef.current = editor;

    // Configure Python language features
    monaco.languages.registerCompletionItemProvider('python', {
      provideCompletionItems: (model, position) => {
        const suggestions: any[] = [];

        // BaseBot class and methods
        suggestions.push({
          label: 'BaseBot',
          kind: monaco.languages.CompletionItemKind.Class,
          insertText: 'BaseBot',
          documentation: 'Base class for all racing bots'
        });

        suggestions.push({
          label: 'on_tick',
          kind: monaco.languages.CompletionItemKind.Method,
          insertText: [
            'def on_tick(self, state):',
            '    """Called every tick (~20Hz) - return your actions."""',
            '    return BotActions(accelerate=True)'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Main decision-making method called every tick'
        });

        suggestions.push({
          label: 'on_checkpoint',
          kind: monaco.languages.CompletionItemKind.Method,
          insertText: [
            'def on_checkpoint(self, checkpoint_index, split_time):',
            '    """Called when passing a checkpoint."""',
            '    pass'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Called when bot passes a checkpoint'
        });

        suggestions.push({
          label: 'on_finish',
          kind: monaco.languages.CompletionItemKind.Method,
          insertText: [
            'def on_finish(self, finish_time, final_position):',
            '    """Called when finishing the race."""',
            '    pass'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Called when bot finishes the race'
        });

        // BotActions
        suggestions.push({
          label: 'BotActions',
          kind: monaco.languages.CompletionItemKind.Class,
          insertText: 'BotActions(${1:accelerate=True})',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Actions the bot can perform'
        });

        // State properties
        suggestions.push({
          label: 'state.car',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'state.car',
          documentation: 'Bot\'s car state (position, speed, heading, etc.)'
        });

        suggestions.push({
          label: 'state.rays',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'state.rays',
          documentation: '7 raycasts for vision (0=forward, 1-3=right, 4-6=left)'
        });

        suggestions.push({
          label: 'state.track',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'state.track',
          documentation: 'Track information (checkpoints, etc.)'
        });

        suggestions.push({
          label: 'state.opponents',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'state.opponents',
          documentation: 'Visible opponent cars (fog of war)'
        });

        suggestions.push({
          label: 'state.race',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'state.race',
          documentation: 'Race progress (checkpoint, position, time)'
        });

        // Memory
        suggestions.push({
          label: 'self.memory',
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: 'self.memory',
          documentation: 'Persistent memory dict (saved between races)'
        });

        return { suggestions };
      }
    });

    // Add hover tooltips
    monaco.languages.registerHoverProvider('python', {
      provideHover: (model, position) => {
        const word = model.getWordAtPosition(position);
        if (!word) return null;

        const hovers: Record<string, string> = {
          'BaseBot': 'Base class for all racing bots. Inherit from this to create your bot.',
          'BotActions': 'Actions to return from on_tick(): accelerate, brake, turn_left, turn_right, use_nitro',
          'on_tick': 'Main method called every tick (~20Hz). Receives BotGameState, returns BotActions.',
          'on_checkpoint': 'Called when passing a checkpoint. Args: checkpoint_index, split_time',
          'on_finish': 'Called when finishing race. Args: finish_time, final_position',
          'rays': 'Array of 7 raycasts: [0]=forward, [1-3]=right side, [4-6]=left side',
          'memory': 'Persistent dict saved between races. Use for learning and stats.'
        };

        const contents = hovers[word.word];
        if (contents) {
          return {
            contents: [{ value: contents }]
          };
        }

        return null;
      }
    });
  };

  return (
    <div style={{ border: '1px solid #444', borderRadius: '4px', overflow: 'hidden' }}>
      <Editor
        height={height}
        defaultLanguage="python"
        value={value}
        onChange={(value) => onChange(value || '')}
        onMount={handleEditorDidMount}
        theme="vs-dark"
        options={{
          minimap: { enabled: true },
          fontSize: 14,
          lineNumbers: 'on',
          roundedSelection: false,
          scrollBeyondLastLine: false,
          readOnly: readOnly,
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          wordWrap: 'on',
          suggest: {
            snippetsPreventQuickSuggestions: false
          }
        }}
      />
    </div>
  );
};
