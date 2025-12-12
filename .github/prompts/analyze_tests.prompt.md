# Test Documentation Improvement

## Workflow
Repeat until `total_functions_to_improve: 0`:
1. Run analysis
2. Document highest priority tests
3. Re-run analysis
4. Continue until zero issues

## Step 1: Analyze
```bash
.venv/bin/python utils/analyze_all_tests.py --pretty
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

## Test Method Template
```python
def test_Method_Scenario_Expected(self):
    """Verifies [behavior] under [conditions].

    Tests [aspect] by [approach].

    Business context:
    [why this matters].

    Arrangement:
    1. Setup step with rationale.
    2. Additional setup with explanation.

    Action:
    What operation is performed and why.

    Assertion Strategy:
    Validates [approach] by confirming:
    - Specific check with context.
    - Additional validation with rationale.

    Testing Principle:
    Validates [principle], ensuring [guarantee].
    """
```

## Test Class Template
```python
class TestClassName:
    """Test suite for ClassName [functionality area].

    Categories:
    1. Initialization Tests - Object creation, initial state (X tests)
    2. Core Functionality - Primary operations, business logic (X tests)
    3. Error Handling - Exceptions, edge cases (X tests)
    4. Integration - Complex scenarios, workflows (X tests)

    Total: X tests.
    """
```

## Priority Requirements
| Priority | Sections |
|----------|----------|
| 8-10 | brief, arrangement, action, assertion, testing principle |
| 5-7 | brief, arrangement, action, assertion |
| 1-4 | brief, action |

## Naming Convention
`test_Method_Scenario_Expected` pattern:
- `test_Connect_ValidConfig_EstablishesConnection`
- `test_Process_InvalidInput_RaisesValueError`
- `test_GetData_EmptyResult_ReturnsNone`

## Constraints
- Documentation only, preserve test logic
- Address missing elements from JSON
- Use plain docstrings (no XML tags)

## Success Criteria
- `total_functions_to_improve: 0`
- All tests rated "excellent"
- No missing sections in any test
