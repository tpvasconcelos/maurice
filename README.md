# Maurice


## Installing

Install and update using `pip`:

```shell
pip install -U maurice
```

## Simple Examples

### Automatic caching

Add any of the following patches at the top of your scripts

Cache SQL queries executed from the pandas library
```python
from maurice.patchers import caching_patch_pandas_db; caching_patch_pandas_db()
import pandas as pd


df = pd.read_sql_query(con=your_connection, sql="select * from your_table")
```

Cache `.fit()` calls from any `sklearn` Estimator (...)
```python
from maurice.patchers import caching_patch_sklearn_estimators; caching_patch_sklearn_estimators()

...
```