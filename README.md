# mindi

A lightweight dependency injection framework for Python.

- Zero external dependencies
- Type hint support
- Automatic singleton instance caching
- Support for both type and string identifiers
- Dependency cycle detection
- Dependency graph verification
- Support for dataclasses and named tuples

## Quick Start

Installation:

```bash
python3 -m pip install mindi
```

A simple example to get you started:

```python
from mindi import Container

di = Container()

@di.bind
class Database:
    def query(self):
        return "data from database"

@di.wire
def main(db: Database = di.use(Database)):
    print(db.query())

main()  # Prints: "data from database"
```

## Examples

### Binding Providers

Bind your providers in multiple ways:

```python
# Simple class binding
@di.bind
class Service:
    pass

# With constructor arguments
@di.bind(url="localhost")
class Database:
    def __init__(self, url):
        self.url = url

# Using string identifiers
di.bind("dev_db", Database, url="dev-host")
di.bind("prod_db", Database, url="prod-host") 

# Using factory functions
di.bind("config", lambda: {"api_key": "secret"})
```

### Dependency Injection

It automatically resolves dependencies marked with `di.use()`:

```python
# Constructor injection
@di.bind
class Service:
    # @di.wire  <== This line is not needed, this is handled by @di.bind
    def __init__(self, db: Database = di.use(Database)):
        self.db = db

# Function injection by type
@di.wire
def handle_request(service: Service = di.use(Service)):
    return service.db.query()

# Function injection by string identifier
di.bind("dev_db", Database)
@di.wire
def handle_dev_request(db = di.use("dev_db")):
    return db.query()
```

### String Identifiers

```python
from mindi import Container
from mindi.core import identifier

di = Container()

class Foo:
    pass

# These binding examples are equivalent:
di.bind(Foo)
di.bind(Foo, Foo)
di.bind(Foo, lambda: Foo())
di.bind(identifier(Foo), Foo)
di.bind(f"{Foo.__module__}.{Foo.__qualname__}", Foo)
```

### Working with Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    api_key: str
    timeout: int = field(default=30)
    database: Database = di.use(Database)

di.bind("config", Config, api_key="secret")

@di.wire
def process(config: Config = di.use("config")):
    print(f"Using API key: {config.api_key}")
    print(f"Database: {config.database.url}")
```

### Wiring Classes and Binding Functions

You can wire both functions and classes:

```python
di.bind("value", lambda: 123)

@di.bind
class Service:
    def __init__(self, value: int = di.use("value")):
        self.value = value

# Create a wired service factory
@di.bind
def WiredService():
    return di.wire(Service)()

@di.wire
def get_value(service: Service = di.use(WiredService)):
    return service.value  # Returns 123
```

### Rebinding for Tests

Dependency overriding for tests:

```python
# Enable rebinding
di = Container(rebind=True)

class MockDatabase:
    def query(self):
        return "test data"

# Override production database with mock
di.bind(Database, lambda: MockDatabase())
```

### Dependency Verification

Verify your dependency graph:

```python
# Verify all dependencies
di.instantiate()

# Verify specific service
db = di.instantiate("db")
```

The framework will detect and report circular dependencies with clear error messages.

## License

MIT License
