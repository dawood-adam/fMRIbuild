# Architectural Patterns

## State Management

### Hook-based State with localStorage Persistence

The app uses React hooks with automatic localStorage sync for persistence across sessions.

**Pattern**: Initialize from localStorage, sync on change via useEffect.

| File | Lines | Description |
|------|-------|-------------|
| src/hooks/useWorkspaces.js | 6-14 | useState with initializer reading from localStorage |
| src/hooks/useWorkspaces.js | 17-24 | Paired useEffect hooks to sync state back to localStorage |

```javascript
// Pattern (not actual code):
const [value, setValue] = useState(() => JSON.parse(localStorage.getItem('key')))
useEffect(() => { localStorage.setItem('key', JSON.stringify(value)) }, [value])
```

### Functional State Updates

All state updates use the functional form `setState(prev => {...})` to ensure immutability and prevent race conditions.

| File | Lines | Usage |
|------|-------|-------|
| src/hooks/useWorkspaces.js | 27-30 | addNewWorkspace |
| src/hooks/useWorkspaces.js | 35-39 | clearCurrentWorkspace |
| src/hooks/useWorkspaces.js | 44-48 | updateCurrentWorkspaceItems |
| src/hooks/useWorkspaces.js | 52-64 | removeCurrentWorkspace |
| src/components/workflowCanvas.jsx | 61-69 | Node updates |
| src/components/workflowCanvas.jsx | 75-91 | Edge updates via onConnect |

---

## Component Patterns

### Functional Components Only

All components are functional (no class components). Two types:

**Stateful Components** (with internal state):
- src/components/headerBar.jsx:5-34 - Modal state
- src/components/NodeComponent.jsx:6-109 - Modal + text input state
- src/components/workflowCanvas.jsx:23-220 - Complex state with refs

**Presentational Components** (props only):
- src/components/actionsBar.jsx:5 - Receives 5 callback props
- src/components/workflowMenuItem.jsx:4 - Simple display
- src/components/toggleWorkflowBar.jsx:4 - Data + onChange callback
- src/components/footer.jsx:4-18 - Pure presentational

### Callback Prop Injection

Parent components create callbacks and pass them to children for event handling.

| File | Lines | Pattern |
|------|-------|---------|
| src/components/workflowCanvas.jsx | 42, 119 | Creates `onSaveParameters` callback inline |
| src/components/NodeComponent.jsx | 37-43 | Executes callback: `if (typeof data.onSaveParameters === 'function')` |

---

## Custom Hooks

### Hooks Returning Objects

Custom hooks export functions that return objects with methods/data.

| Hook | File | Returns |
|------|------|---------|
| useWorkspaces | src/hooks/useWorkspaces.js:67-75 | `{workspaces, currentWorkspace, setCurrentWorkspace, addNewWorkspace, clearCurrentWorkspace, updateCurrentWorkspaceItems, removeCurrentWorkspace}` |
| useGenerateWorkflow | src/hooks/generateWorkflow.js:6-75 | `{generateWorkflow}` |

### Pure Utility Functions

`buildCWLWorkflow` in src/hooks/buildWorkflow.js:12 is a pure function (not a hook) with internal helpers:
- `nodeById`, `inEdgesOf`, `outEdgesOf` (lines 16-18)
- `toCWLType` (lines 80-100)
- `makeWfInputName` (lines 103-105)
- Kahn's algorithm for cycle detection (lines 20-36)

---

## Error Handling

### Multi-tier Strategy

**Console Logging** (development):
- src/hooks/generateWorkflow.js:14, 51 - `console.error()` for critical
- src/components/workflowMenu.jsx:25 - `console.warn()` for non-blocking

**User Alerts** (production-facing):
- src/hooks/generateWorkflow.js:20, 29, 66 - `alert('Message:\n${err.message}')`
- src/components/NodeComponent.jsx:41 - JSON parse error feedback

**Graceful Degradation**:
- src/hooks/generateWorkflow.js:45-52 - README fetch failure doesn't stop workflow generation
- src/components/NodeComponent.jsx:37-43 - JSON parse failure falls back to raw text

### Try-Catch Scoping

Errors are caught at the operation level, not globally:
- src/hooks/buildWorkflow.js:35 - Throws for cycles
- src/hooks/buildWorkflow.js:114 - Throws for missing tool mappings
- src/hooks/generateWorkflow.js:26-31 - Catches and handles build errors

---

## Side Effect Patterns

### useEffect for Synchronization

| File | Lines | Purpose |
|------|-------|---------|
| src/hooks/useWorkspaces.js | 17-24 | Sync state to localStorage |
| src/components/workflowCanvas.jsx | 33-50 | Sync workflowItems prop to canvas state |
| src/components/workflowCanvas.jsx | 156-170 | Global keydown listener for Delete key |

### useCallback for Stable References

Prevents infinite loops and unnecessary re-renders:
- src/components/workflowCanvas.jsx:73-94 - `onConnect` with deps `[nodes, edges, updateCurrentWorkspaceItems]`
- src/components/workflowCanvas.jsx:130-153 - `onNodesDelete` with deps `[updateCurrentWorkspaceItems]`

---

## File Organization

### Naming Conventions

- **Components**: camelCase files, PascalCase exports (exception: `NodeComponent.jsx`)
- **Hooks**: camelCase with `use` prefix for hook files
- **Styles**: Paired 1:1 with component names in `src/styles/`

### Import Pattern

Each component imports its paired CSS:
```javascript
import '../styles/componentName.css'
```

---

## Data Shapes

No TypeScript - implicit interfaces via consistent structure:

**Node**:
```javascript
{ id, type, data: { label, parameters, onSaveParameters }, position: {x, y} }
```

**Edge**:
```javascript
{ source, target, animated?, markerEnd?, style? }
```

**Workspace**:
```javascript
{ nodes: [], edges: [] }
```

**Tool (from TOOL_MAP)**:
```javascript
{ id, cwlPath, requiredInputs, optionalInputs, primaryOutputs, outputs }
```
