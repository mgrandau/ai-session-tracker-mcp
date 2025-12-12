# Source Documentation Improvement

## Workflow
Repeat until `total_functions_to_improve: 0`:
1. Run analysis
2. Document highest priority functions
3. Re-run analysis
4. Continue until zero issues

## Step 1: Analyze
```bash
.venv/bin/python utils/analyze_all_source.py --pretty
```

## Step 2: Document by Priority
- **8-10**: Full docstrings immediately
- **5-7**: Add missing sections
- **1-4**: Complete all remaining

## Step 3: Re-analyze and Repeat
Re-run analysis after each batch. Continue until:
```json
"total_functions_to_improve": 0
```

## Function Template (Google Style)
```python
def func(param1: T1, param2: T2) -> RT:
    """Brief summary.

    Detailed purpose/behavior. Business context: why this matters.

    Args:
        param1: Type, constraints, valid ranges, examples.
        param2: Type, units, defaults, relation to other params.

    Returns:
        Type, structure, value ranges, edge cases.

    Raises:
        ValueError: When param1 < 0.
        TypeError: Invalid param types.

    Example:
        >>> result = func(val1, val2)
        >>> func(edge, config={'opt': True})
    """
```

## Class Template
```python
class Name:
    """Brief summary.

    Detailed role/usage. Business context: why this exists.

    Attributes:
        attr: Type, purpose, constraints.

    Raises:
        ValueError: Init error conditions.

    Example:
        >>> obj = Name(config)
        >>> obj.method()
    """
```

## Priority Requirements
| Priority | Sections |
|----------|----------|
| 8-10 | brief, detailed, business context, args, returns, raises, example |
| 5-7 | brief, detailed, args, returns, raises |
| 1-4 | brief, args, returns |

## Constraints
- Documentation only, preserve functionality
- Address missing elements from JSON
- Business context for public APIs

## Success Criteria
- `total_functions_to_improve: 0`
- All functions rated "excellent"
- No missing sections in any function
