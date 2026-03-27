"""
Тест для демонстрации РЕШЕНИЯ проблемы race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_safe() заказ оплачивается только один раз.
"""

import asyncio
import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.application.payment_service import PaymentService
from app.domain.exceptions import OrderAlreadyPaidError


# TODO: Настроить подключение к тестовой БД
# DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/marketplace"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание сессии
    # raise NotImplementedError("TODO: Реализовать db_session fixture")
    async with AsyncSessionLocal() as session:
        yield session
        

@pytest.fixture
async def test_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание тестового заказа
    # raise NotImplementedError("TODO: Реализовать test_order fixture")
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    async with db_session.begin():
        await db_session.execute(
            text("INSERT INTO users (id, email, name, created_at) VALUES (:id, :email, :name, NOW())"),
            {"id": str(user_id), "email": f"safe_{user_id}@example.com", "name": "Test User"},
        )
        await db_session.execute(
            text("INSERT INTO orders (id, user_id, status, total_amount, created_at) VALUES (:id, :user_id, 'created', 100.00, NOW())"),
            {"id": str(order_id), "user_id": str(user_id)},
        )
        await db_session.execute(
            text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'created', NOW())"),
            {"order_id": str(order_id)},
        )

    yield order_id

    # Очищаем данные после теста
    async with AsyncSessionLocal() as cleanup_session:
        async with cleanup_session.begin():
            await cleanup_session.execute(
                text("DELETE FROM order_status_history WHERE order_id = :id"),
                {"id": str(order_id)},
            )
            await cleanup_session.execute(
                text("DELETE FROM orders WHERE id = :id"),
                {"id": str(order_id)},
            )
            await cleanup_session.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": str(user_id)},
            )

@pytest.mark.asyncio
async def test_concurrent_payment_safe_prevents_race_condition(db_session, test_order):
    """
    Тест демонстрирует решение проблемы race condition с помощью pay_order_safe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен только один раз.
    Это показывает, что метод pay_order_safe() защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_safe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_safe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_safe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить результаты:
       - Одна попытка должна УСПЕШНО завершиться
       - Вторая попытка должна выбросить OrderAlreadyPaidError ИЛИ вернуть ошибку
       
       success_count = sum(1 for r in results if not isinstance(r, Exception))
       error_count = sum(1 for r in results if isinstance(r, Exception))
       
       assert success_count == 1, "Ожидалась одна успешная оплата"
       assert error_count == 1, "Ожидалась одна неудачная попытка"
       
    4. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ОДНУ ЗАПИСЬ 'paid' - проблема решена!
       assert len(history) == 1, "Ожидалась 1 запись об оплате (БЕЗ RACE CONDITION!)"
       
    5. Вывести информацию об успешном решении:
       
       print(f"✅ RACE CONDITION PREVENTED!")
       print(f"Order {order_id} was paid only ONCE:")
       print(f"  - {history[0]['changed_at']}: status = {history[0]['status']}")
       print(f"Second attempt was rejected: {results[1]}")
    """
    # TODO: Реализовать тест, демонстрирующий решение race condition
    # raise NotImplementedError("TODO: Реализовать test_concurrent_payment_safe")
    order_id = test_order

    async def payment_attempt_1():
        async with AsyncSessionLocal() as session1:
            service = PaymentService(session1)
            return await service.pay_order_safe(order_id)

    async def payment_attempt_2():
        async with AsyncSessionLocal() as session2:
            service = PaymentService(session2)
            return await service.pay_order_safe(order_id)

    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True,
    )

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    error_count = sum(1 for r in results if isinstance(r, Exception))

    # Проверяем историю
    service = PaymentService(db_session)
    history = await service.get_payment_history(order_id)

    print(f"\n✅ RACE CONDITION PREVENTED!")
    print(f"Order {order_id} was paid only ONCE:")
    for record in history:
        print(f"  - {record['changed_at']}: status = {record['status']}")
    print(f"Second attempt was rejected: {results[1] if isinstance(results[1], Exception) else results[0]}")

    assert success_count == 1, f"Ожидалась одна успешная оплата, получено: {success_count}"
    assert error_count == 1, f"Ожидалась одна неудачная попытка, получено: {error_count}"
    assert len(history) == 1, f"Ожидалась 1 запись (БЕЗ RACE CONDITION!), получено: {len(history)}"


@pytest.mark.asyncio
async def test_concurrent_payment_safe_with_explicit_timing():
    """
    Дополнительный тест: проверить работу блокировок с явной задержкой.
    
    TODO: Реализовать тест с добавлением задержки в первой транзакции:
    
    1. Первая транзакция:
       - Начать транзакцию
       - Заблокировать заказ (FOR UPDATE)
       - Добавить задержку (asyncio.sleep(1))
       - Оплатить
       - Commit
       
    2. Вторая транзакция (запустить через 0.1 секунды после первой):
       - Начать транзакцию
       - Попытаться заблокировать заказ (FOR UPDATE)
       - ДОЛЖНА ЖДАТЬ освобождения блокировки от первой транзакции
       - После освобождения - увидеть обновленный статус 'paid'
       - Выбросить OrderAlreadyPaidError
       
    3. Проверить временные метки:
       - Вторая транзакция должна завершиться ПОЗЖЕ первой
       - Разница должна быть >= 1 секунды (время задержки)
       
    Это подтверждает, что FOR UPDATE действительно блокирует строку.
    """
    # TODO: Реализовать тест с проверкой блокировки
    # raise NotImplementedError("TODO: Реализовать test_concurrent_payment_safe_with_explicit_timing")
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO users (id, email, name, created_at) VALUES (:id, :email, :name, NOW())"),
                {"id": str(user_id), "email": f"timing_{user_id}@example.com", "name": "Test"},
            )
            await session.execute(
                text("INSERT INTO orders (id, user_id, status, total_amount, created_at) VALUES (:id, :user_id, 'created', 100.00, NOW())"),
                {"id": str(order_id), "user_id": str(user_id)},
            )
            await session.execute(
                text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'created', NOW())"),
                {"order_id": str(order_id)},
            )

    import time

    async def slow_payment():
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                # Блокируем строку
                await session.execute(
                    text("SELECT status FROM orders WHERE id = :id FOR UPDATE"),
                    {"id": str(order_id)},
                )
                # Задержка пока держим блокировку
                await asyncio.sleep(1)
                await session.execute(
                    text("UPDATE orders SET status = 'paid' WHERE id = :id AND status = 'created'"),
                    {"id": str(order_id)},
                )
                await session.execute(
                    text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'paid', NOW())"),
                    {"order_id": str(order_id)},
                )
        return time.time()

    async def fast_payment():
        await asyncio.sleep(0.1)  # Стартуем чуть позже
        start = time.time()
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            try:
                await service.pay_order_safe(order_id)
            except Exception as e:
                pass
        return time.time() - start

    t1, wait_time = await asyncio.gather(slow_payment(), fast_payment())

    print(f"\n⏱️ Вторая транзакция ждала блокировку: {wait_time:.2f} сек")
    assert wait_time >= 0.9, "Вторая транзакция должна была ждать блокировку от первой"

    # Очистка
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {"id": str(order_id)})
            await session.execute(text("DELETE FROM orders WHERE id = :id"), {"id": str(order_id)})
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})


@pytest.mark.asyncio
async def test_concurrent_payment_safe_multiple_orders():
    """
    Дополнительный тест: проверить, что блокировки не мешают разным заказам.
    
    TODO: Реализовать тест:
    1. Создать ДВА разных заказа
    2. Оплатить их ПАРАЛЛЕЛЬНО с помощью pay_order_safe()
    3. Проверить, что ОБА успешно оплачены
    
    Это показывает, что FOR UPDATE блокирует только конкретную строку,
    а не всю таблицу, что важно для производительности.
    """
    # TODO: Реализовать тест с несколькими заказами
    # raise NotImplementedError("TODO: Реализовать test_concurrent_payment_safe_multiple_orders")
    user_id = uuid.uuid4()
    order_id_1 = uuid.uuid4()
    order_id_2 = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO users (id, email, name, created_at) VALUES (:id, :email, :name, NOW())"),
                {"id": str(user_id), "email": f"multi_{user_id}@example.com", "name": "Test"},
            )
            for oid in [order_id_1, order_id_2]:
                await session.execute(
                    text("INSERT INTO orders (id, user_id, status, total_amount, created_at) VALUES (:id, :user_id, 'created', 100.00, NOW())"),
                    {"id": str(oid), "user_id": str(user_id)},
                )
                await session.execute(
                    text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'created', NOW())"),
                    {"order_id": str(oid)},
                )

    async def pay(order_id):
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            return await service.pay_order_safe(order_id)

    results = await asyncio.gather(pay(order_id_1), pay(order_id_2), return_exceptions=True)

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    print(f"\nДва разных заказа оплачены параллельно: {success_count}/2 успешно")
    assert success_count == 2, "Оба заказа должны быть успешно оплачены"

    # Очистка
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for oid in [order_id_1, order_id_2]:
                await session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {"id": str(oid)})
                await session.execute(text("DELETE FROM orders WHERE id = :id"), {"id": str(oid)})
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})


if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_safe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_safe_prevents_race_condition PASSED
    
    Вывод должен показывать:
    ✅ RACE CONDITION PREVENTED!
    Order XXX was paid only ONCE:
      - 2024-XX-XX: status = paid
    Second attempt was rejected: OrderAlreadyPaidError(...)
    """
    pytest.main([__file__, "-v", "-s"])
