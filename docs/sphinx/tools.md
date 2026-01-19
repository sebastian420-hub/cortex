# Tools Reference

Cortex provides a rich set of built-in tools for various tasks.

## File Operations

### read_file

Read the contents of a file with optional line range.

```python
read_file(path="src/main.py", offset=0, limit=100)
```

### write_file

Write content to a file (creates parent directories if needed).

```python
write_file(path="output.txt", content="Hello, World!")
```

### edit

Edit a file using search and replace.

```python
edit(path="config.py", old_string="DEBUG = False", new_string="DEBUG = True")
```

## Search Tools

### grep

Search file contents using regex patterns.

```python
grep(pattern="def .*:", path="src/", file_type="py")
```

### glob

Find files matching a glob pattern.

```python
glob(pattern="**/*.py", path="src/")
```

## Git Tools

### git_status

Show the current repository status.

```python
git_status()
```

### git_diff

Show changes in the working directory.

```python
git_diff(staged=False, file="specific_file.py")
```

## AST Tools

### ast_search

Search code using AST patterns (requires tree-sitter).

```python
ast_search(pattern="function:calculate*", path="src/")
```

### ast_extract

Extract specific code elements.

```python
ast_extract(element="class", name="MyClass", path="src/models.py")
```

## Web Tools

### web_fetch

Fetch and parse web page content.

```python
web_fetch(url="https://example.com", selector="main")
```

### web_search

Search the web for information.

```python
web_search(query="python async best practices")
```

## Creating Custom Tools

See {doc}`plugin_development` for creating your own tools.
