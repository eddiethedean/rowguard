# Python API reference

**Signatures and members only.** For parameter contracts, rejection policies,
SQLRules defaults, and async caveats, use the narrative
[API guide](../api.md) and [error catalog](errors.md).

## Entry points

```{eval-rst}
.. autofunction:: rowguard.select
.. autofunction:: rowguard.execute
.. autofunction:: rowguard.stream
.. autofunction:: rowguard.aselect
.. autofunction:: rowguard.aexecute
.. autofunction:: rowguard.astream
.. autofunction:: rowguard.validate_rows
.. autofunction:: rowguard.compile_plan
```

## Results and planning

```{eval-rst}
.. autoclass:: rowguard.QueryResult
   :members:
   :undoc-members:

.. autoclass:: rowguard.StreamResult
   :members:
   :undoc-members:

.. autoclass:: rowguard.AsyncStreamResult
   :members:
   :undoc-members:

.. autoclass:: rowguard.RejectedRow
   :members:
   :undoc-members:

.. autoclass:: rowguard.QueryStatistics
   :members:
   :undoc-members:

.. autoclass:: rowguard.ExecutionPlan
   :members:
   :undoc-members:
```

## Observers and errors

```{eval-rst}
.. autoclass:: rowguard.StreamObserver
   :members:
   :undoc-members:

.. autoclass:: rowguard.BaseStreamObserver
   :members:
   :undoc-members:

.. autoexception:: rowguard.RowGuardError
   :show-inheritance:

.. autoexception:: rowguard.ConfigurationError
   :show-inheritance:

.. autoexception:: rowguard.PlanningError
   :show-inheritance:

.. autoexception:: rowguard.QueryExecutionError
   :show-inheritance:

.. autoexception:: rowguard.RowValidationError
   :show-inheritance:

.. autoexception:: rowguard.RowAdaptationError
   :show-inheritance:

.. autoexception:: rowguard.RejectHandlerError
   :show-inheritance:
```
