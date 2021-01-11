# Todos

## Features

- Add a registry to patched objects
- Add ability to unpatch objects
- Add context manager to temporarily add or remove patches

### General Data Science
- Smart-bins from input data

### pandas

- did you mean `.value_counts()` ?
- Styling preset

## Bugs

How can this happen?
```text
---------------------------------------------------------------------------
FileExistsError                           Traceback (most recent call last)
<ipython-input-27-9512cbff5263> in <module>
----> 1 df = run_query(sql_query)
      2 display(df)

~/Library/Caches/pypoetry/virtualenvs/reclib-SL8Kyh7D-py3.7/lib/python3.7/site-packages/tiqds/db.py in run_query(sql_query, query_params, connection, max_retries)
    285 
    286     query = Query(sql_query=sql_query, connection=connection, query_params=query_params)
--> 287     query.run()
    288     return query.result
    289 

~/Library/Caches/pypoetry/virtualenvs/reclib-SL8Kyh7D-py3.7/lib/python3.7/site-packages/tiqds/db.py in run(self)
    151         values (the result)."""
    152         with self.connection as conn:
--> 153             self.result = pd.read_sql_query(con=conn, sql=self.sql, params=self.params, chunksize=self.chunksize)
    154         self._result_cached = self.result
    155         # TODO: return the instance s.t. `df = query.run().result` ?

~/Library/Caches/pypoetry/virtualenvs/reclib-SL8Kyh7D-py3.7/lib/python3.7/site-packages/pandas/io/sql.py in read_sql_query(sql, con, index_col, coerce_float, params, parse_dates, chunksize)
    381         coerce_float=coerce_float,
    382         parse_dates=parse_dates,
--> 383         chunksize=chunksize,
    384     )
    385 

~/Library/Caches/pypoetry/virtualenvs/reclib-SL8Kyh7D-py3.7/lib/python3.7/site-packages/maurice/patchers/core.py in _caching_method_wrapper(method, instance, args, kwargs, save_state)
     68             self._path_to_cached_method.mkdir(parents=True, exist_ok=False)
     69             if self._save_state:
---> 70                 self._path_to_state.write_bytes(dill.dumps(self._get_instance_state()))
     71             self._path_to_result.write_bytes(dill.dumps(result))
     72             return result

~/Library/Caches/pypoetry/virtualenvs/reclib-SL8Kyh7D-py3.7/lib/python3.7/site-packages/maurice/patchers/core.py in run_wrapped(self)
     53             state: dict = getattr(self._instance, "__getstate__")()
     54         else:
---> 55             state = self._instance.__dict__
     56         return state
     57 

~/.pyenv/versions/3.7.9/lib/python3.7/pathlib.py in mkdir(self, mode, parents, exist_ok)
   1271             self._raise_closed()
   1272         try:
-> 1273             self._accessor.mkdir(self, mode)
   1274         except FileNotFoundError:
   1275             if not parents or self.parent == self:

FileExistsError: [Errno 17] File exists: '/Users/tpvasconcelos/PycharmProjects/recommendations/adhoc/top_products_in_venue/.maurice_cache/pandas/io/sql/SQLiteDatabase/ignore_state/read_query/00db048dac38086adad5334e768fb2dc'
```