# Todos

## Features

- Add a registry to patched objects
- Add ability to unpatch objects
- Add context manager to temporarily add or remove patches

### Settings and config
```text
❯ jupyter lab path
Application directory:   /Users/tpvasconcelos/Library/Caches/pypoetry/virtualenvs/dca-9Qm21AwB-py3.7/share/jupyter/lab
User Settings directory: /Users/tpvasconcelos/.jupyter/lab/user-settings
Workspaces directory: /Users/tpvasconcelos/.jupyter/lab/workspaces
```


### General Data Science
- Smart-bins from input data
  - Implement this <https://8080labs.com/blog/posts/find-best-bins-for-plotly-histogram/>
- Look into <https://bamboolib.8080labs.com/>

### pandas

- did you mean `.value_counts()` ?
- Styling preset
- The pandas SQLDatabase and SQLiteDatabase caching patches still try to connect to DB before accessing the
  cache this is probably happening during instantiation of the class. This makes the caching unusable when
  unconnected to the internet.

## Bugs

- FileExistsError when a method is patched multiple times.
  The solution is to create a registry for patched methods
  such that we don't double-patch methods.
