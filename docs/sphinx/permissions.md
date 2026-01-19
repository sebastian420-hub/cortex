# Permission Modes

Cortex supports three permission modes to control what actions can be performed.

## Normal Mode (default)

In normal mode, Cortex asks for confirmation before:
- Writing or editing files
- Executing commands
- Making git commits

```bash
cortex --permission normal
```

## Auto-Approve Mode

In auto-approve mode, Cortex executes all actions without asking for confirmation.

```bash
cortex --permission auto
```

```{warning}
Use auto-approve mode with caution. All file modifications and command executions will happen automatically.
```

## Plan Mode

In plan mode, Cortex can only perform read operations. All write operations are blocked.

```bash
cortex --permission plan
```

This is useful for:
- Exploring a codebase safely
- Generating plans without executing them
- Reviewing what actions would be taken

## Comparison

| Action | Normal | Auto | Plan |
|--------|--------|------|------|
| Read files | Yes | Yes | Yes |
| Search files | Yes | Yes | Yes |
| Write files | Ask | Yes | No |
| Execute commands | Ask | Yes | No |
| Git operations | Ask | Yes | No |
