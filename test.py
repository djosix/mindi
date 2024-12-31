#!/usr/bin/env python3

import unittest
from mindi import Container
from mindi.core import identifier
from datetime import datetime
from dataclasses import dataclass, field
from typing import NamedTuple


class TestMindiContainer(unittest.TestCase):
    def test_basic_binding(self):
        """Test basic class binding and injection"""
        di = Container()

        @di.bind
        class Service:
            def get_value(self):
                return "value"

        @di.wire
        def use_service(svc: Service = di.use(Service)):
            return svc.get_value()

        self.assertEqual(use_service(), "value")

    def test_singleton_behavior(self):
        """Test that bound instances are reused (singleton behavior)"""
        di = Container()

        @di.bind
        class Service:
            pass

        @di.wire
        def get_service1(svc: Service = di.use(Service)):
            return svc

        @di.wire
        def get_service2(svc: Service = di.use(Service)):
            return svc

        self.assertIs(get_service1(), get_service2())

    def test_constructor_injection(self):
        """Test dependency injection in constructor"""
        di = Container()

        @di.bind
        class Database:
            def get_data(self):
                return "data"

        @di.bind
        class Service:
            def __init__(self, db: Database = di.use(Database)):
                self.db = db

        @di.wire
        def use_service(svc: Service = di.use(Service)):
            return svc.db.get_data()

        self.assertEqual(use_service(), "data")

    def test_string_identifiers(self):
        """Test binding and using with string identifiers"""
        di = Container()

        class Config:
            def __init__(self, env: str):
                self.env = env

        di.bind("dev_config", Config, env="dev")
        di.bind("prod_config", Config, env="prod")

        @di.wire
        def get_configs(
            dev: Config = di.use("dev_config"),
            prod: Config = di.use("prod_config")
        ):
            return dev.env, prod.env

        dev_env, prod_env = get_configs()
        self.assertEqual(dev_env, "dev")
        self.assertEqual(prod_env, "prod")

    def test_factory_binding(self):
        """Test binding with factory functions"""
        di = Container()

        def create_config(api_key):
            return {"api_key": api_key}

        di.bind("config", create_config, api_key="secret")

        @di.wire
        def get_config(config: dict = di.use("config")):
            return config["api_key"]

        self.assertEqual(get_config(), "secret")

    def test_rebinding(self):
        """Test rebinding when allowed"""
        di = Container(rebind=True)

        @di.bind
        class Service:
            def get_value(self):
                return "original"

        @di.wire
        def use_service(svc: Service = di.use(Service)):
            return svc.get_value()

        self.assertEqual(use_service(), "original")

        # Rebind to new implementation
        @di.bind
        class Service:
            def get_value(self):
                return "new"

        self.assertEqual(use_service(), "new")

    def test_rebinding_not_allowed(self):
        """Test rebinding when not allowed"""
        di = Container(rebind=False)

        class Service:
            pass
        
        di.bind(Service)

        with self.assertRaises(KeyError):
            di.bind(Service)

    def test_cross_module_reference(self):
        """Test referring to types from other modules"""
        di = Container()

        di.bind(datetime, year=2025, month=1, day=1)

        @di.wire
        def get_datetime1(dt: datetime = di.use(datetime)):
            return dt

        @di.wire
        def get_datetime2(dt: datetime = di.use(identifier(datetime))):
            return dt

        @di.wire
        def get_datetime3(dt: datetime = di.use(f"{datetime.__module__}.{datetime.__qualname__}")):
            return dt

        self.assertTrue(get_datetime1(), datetime(2025, 1, 1))
        self.assertTrue(get_datetime2(), datetime(2025, 1, 1))
        self.assertTrue(get_datetime3(), datetime(2025, 1, 1))

    def test_dependency_override(self):
        """Test overriding dependencies for testing"""
        di = Container(rebind=True)

        class Database:
            def query(self):
                return "real data"

        class MockDatabase:
            def query(self):
                return "mock data"

        di.bind(Database)

        @di.wire
        def get_data(db: Database = di.use(Database)):
            return db.query()

        self.assertEqual(get_data(), "real data")

        # Override with mock
        di.bind(Database, lambda: MockDatabase())
        self.assertEqual(get_data(), "mock data")

    def test_multiple_dependencies(self):
        """Test complex dependency chain"""
        di = Container()

        @di.bind
        class ServiceA:
            def get_value(self):
                return "A"

        @di.bind
        class ServiceB:
            @di.wire
            def __init__(self, svc_a: ServiceA = di.use(ServiceA)):
                self.svc_a = svc_a

            def get_value(self):
                return f"B+{self.svc_a.get_value()}"

        @di.bind
        class ServiceC:
            @di.wire
            def __init__(self,
                         svc_a: ServiceA = di.use(ServiceA),
                         svc_b: ServiceB = di.use(ServiceB)
                         ):
                self.svc_a = svc_a
                self.svc_b = svc_b

            def get_value(self):
                return f"C+{self.svc_a.get_value()}+{self.svc_b.get_value()}"

        @di.wire
        def use_services(
            a: ServiceA = di.use(ServiceA),
            b: ServiceB = di.use(ServiceB),
            c: ServiceC = di.use(ServiceC)
        ):
            return [a.get_value(), b.get_value(), c.get_value()]

        results = use_services()
        self.assertEqual(results[0], "A")
        self.assertEqual(results[1], "B+A")
        self.assertEqual(results[2], "C+A+B+A")

    def test_wired_class(self):
        """Test binding and wiring a class"""
        di = Container()

        di.bind("value", lambda: 87)

        @di.bind
        class Service:
            def __init__(self, value: int = di.use("value")):
                self.value = value

        @di.bind
        def WiredService():
            return di.wire(Service)()

        @di.wire
        def func1(svc: Service = di.use(Service)) -> int:
            return svc.value

        @di.wire
        def func2(svc: Service = di.use(WiredService)) -> int:
            return svc.value

        self.assertEqual(Service().value, di.use("value"))
        self.assertEqual(WiredService().value, 87)
        self.assertEqual(func1(), 87)
        self.assertEqual(func2(), 87)

    def test_mixed_parameters(self):
        """Test mixing normal parameters with di.use parameters"""
        di = Container()

        @di.bind
        class Database:
            def query(self):
                return "data"

        @di.bind(value="injected")
        class Config:
            def __init__(self, value):
                self.value = value

        # Test mixing required and injected params
        @di.wire
        def func1(name: str, db: Database = di.use(Database)):
            return f"{name} got {db.query()}"

        self.assertEqual(func1("test"), "test got data")

        # Test mixing injected and default params
        @di.wire
        def func2(
            db: Database = di.use(Database),
            name: str = "default",
            config: Config = di.use(Config)
        ):
            return f"{name} got {db.query()} with {config.value}"

        self.assertEqual(func2(), "default got data with injected")
        self.assertEqual(func2(name="custom"), "custom got data with injected")

        # Test positional and keyword arguments
        @di.wire
        def func3(x: int, y: int, db: Database = di.use(Database)):
            return f"x={x} y={y} data={db.query()}"

        self.assertEqual(func3(1, 2), "x=1 y=2 data=data")
        self.assertEqual(func3(1, y=2), "x=1 y=2 data=data")
        self.assertEqual(func3(x=1, y=2), "x=1 y=2 data=data")

    def test_dataclass_and_namedtuple(self):
        """Test injection of dataclass and namedtuple"""
        di = Container()

        di.bind("value3", lambda: 3)

        class Foo:
            value1: int
            value2: int = field(default=2)
            value3: int = di.use("value3")

        class Bar(NamedTuple):
            value: int

        di.bind("Foo1", dataclass()(Foo), value1=1)
        di.bind("Foo2", dataclass(slots=True)(Foo), value1=1)
        di.bind("Bar", Bar, value=4)

        @di.wire
        def func(
            foo1: Foo = di.use("Foo1"),
            foo2: Foo = di.use("Foo2"),
            bar: Bar = di.use("Bar"),
        ):
            self.assertEqual(foo1.value1, 1)
            self.assertEqual(foo1.value2, 2)
            self.assertEqual(foo1.value3, 3)
            self.assertEqual(foo2.value1, 1)
            self.assertEqual(foo2.value2, 2)
            self.assertEqual(foo2.value3, 3)
            self.assertEqual(bar.value, 4)

        func()

    def test_error_handling(self):
        """Test various error conditions"""
        di = Container()

        # Test missing provider
        @di.wire
        def use_missing(svc=di.use("missing")):
            return svc

        with self.assertRaises(KeyError):
            use_missing()

        # Test invalid bind arguments
        with self.assertRaises(TypeError):
            di.bind(123)  # Invalid ID type

        with self.assertRaises(TypeError):
            di.bind("key", 123)  # Non-callable provider

        # Test invalid use arguments
        with self.assertRaises(TypeError):
            di.use(123)  # Invalid ID type

    def test_linear_dependency_chain(self):
        """Test a linear dependency chain without cycles.

        Dependency chain: A -> B -> C -> D
        Should successfully instantiate all dependencies.
        """
        di = Container()

        class A:
            def __init__(self, s=di.use("B")): ...

        class B:
            def __init__(self, s=di.use("C")): ...

        class C:
            def __init__(self, s=di.use("D")): ...

        class D:
            def __init__(self): ...

        # Bind all services in linear chain
        di.bind("A", A)
        di.bind("B", B)
        di.bind("C", C)
        di.bind("D", D)

        # Should complete without errors
        di.instantiate()

    def test_cyclic_dependency_detection(self):
        """Test detection of circular dependencies.

        Dependency chain: A -> B -> C -> D -> B
        Should raise RuntimeError with clear cycle description.
        """
        di = Container()

        class A:
            def __init__(self, s=di.use("B")): ...

        class B:
            def __init__(self, s=di.use("C")): ...

        class C:
            def __init__(self, s=di.use("D")): ...

        class D:
            def __init__(self, s=di.use("B")): ...  # Creates cycle back to B

        # Bind all services in circular chain
        di.bind("A", A)
        di.bind("B", B)
        di.bind("C", C)
        di.bind("D", D)

        # Should raise RuntimeError with cycle description
        with self.assertRaises(RuntimeError) as cm:
            di.instantiate()

        self.assertEqual(
            str(cm.exception),
            "Cycle detected: B -> C -> D -> B"
        )


if __name__ == "__main__":
    unittest.main(verbosity=1)
