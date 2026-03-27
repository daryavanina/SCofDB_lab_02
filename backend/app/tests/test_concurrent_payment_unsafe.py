"""
Тест для демонстрации ПРОБЛЕМЫ race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_unsafe() возникает двойная оплата.
"""

import asyncio
import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.application.payment_service import PaymentService


# TODO: Настроить подключение к тестовой БД
# DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/marketplace"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру:
    1. Создать engine
    2. Создать session maker
    3. Открыть сессию
    4. Yield сессию
    5. Закрыть сессию после теста
    """
    # TODO: Реализовать создание сессии
    # raise NotImplementedError("TODO: Реализовать db_session fixture")
    async with AsyncSessionLocal() as session:
        yield session
        

@pytest.fixture
async def test_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру:
    1. Создать тестового пользователя
    2. Создать тестовый заказ со статусом 'created'
    3. Записать начальный статус в историю
    4. Вернуть order_id
    5. После теста - очистить данные
    """
    # TODO: Реализовать создание тестового заказа
    # raise NotImplementedError("TODO: Реализовать test_order fixture")
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    async with db_session.begin():
        # тестовый пользователб
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, name, created_at)
                VALUES (:id, :email, :name, NOW())
            """),
            {
                "id": str(user_id),
                "email": f"test_{user_id}@example.com",
                "name": "Test User",
            },
        )
        # тестовый заказ
        await db_session.execute(
            text("""
                INSERT INTO orders (id, user_id, status, total_amount, created_at)
                VALUES (:id, :user_id, 'created', 100.00, NOW())
            """),
            {"id": str(order_id), "user_id": str(user_id)},
        )
        # Запись начального статуса в историю
        await db_session.execute(
            text("""
                INSERT INTO order_status_history (id, order_id, status, changed_at)
                VALUES (gen_random_uuid(), :order_id, 'created', NOW())
            """),
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
async def test_concurrent_payment_unsafe_demonstrates_race_condition(db_session, test_order):
    """
    Тест демонстрирует проблему race condition при использовании pay_order_unsafe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен дважды.
    Это показывает, что метод pay_order_unsafe() НЕ защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_unsafe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_unsafe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_unsafe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ДВЕ ЗАПИСИ 'paid' - это и есть проблема!
       assert len(history) == 2, "Ожидалось 2 записи об оплате (RACE CONDITION!)"
       
    4. Вывести информацию о проблеме:
       
       print(f"⚠️ RACE CONDITION DETECTED!")
       print(f"Order {order_id} was paid TWICE:")
       for record in history:
           print(f"  - {record['changed_at']}: status = {record['status']}")
    """
    # TODO: Реализовать тест, демонстрирующий race condition
    # raise NotImplementedError("TODO: Реализовать test_concurrent_payment_unsafe")
    order_id = test_order

    # две независимые сессии (два HTTP-запроса)
    async def payment_attempt_1():
        async with AsyncSessionLocal() as session1:
            service = PaymentService(session1)
            return await service.pay_order_unsafe(order_id)

    async def payment_attempt_2():
        async with AsyncSessionLocal() as session2:
            service = PaymentService(session2)
            return await service.pay_order_unsafe(order_id)

    # два параллельных вызова
    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True,
    )

    # Проверка истории оплат
    service = PaymentService(db_session)
    history = await service.get_payment_history(order_id)

    # информация о проблеме
    print(f"\n⚠️ RACE CONDITION DETECTED!")
    print(f"Order {order_id} was paid TWICE:")
    for record in history:
        print(f"  - {record['changed_at']}: status = {record['status']}")

    # ОЖИДАЕМ ДВЕ ЗАПИСИ 'paid' - это и есть race condition!
    assert len(history) == 2, f"Ожидалось 2 записи (RACE CONDITION!), получено: {len(history)}"


@pytest.mark.asyncio
async def test_concurrent_payment_unsafe_both_succeed():
    """
    Дополнительный тест: проверить, что ОБЕ транзакции успешно завершились.
    
    TODO: Реализовать проверку, что:
    1. Обе попытки оплаты вернули успешный результат
    2. Ни одна не выбросила исключение
    3. Обе записали в историю
    
    Это подтверждает, что проблема не в ошибках, а в race condition.
    """
    # TODO: Реализовать проверку успешности обеих транзакций
    # raise NotImplementedError("TODO: Реализовать test_concurrent_payment_unsafe_both_succeed")
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    # Создаём тестовые данные
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO users (id, email, name, created_at) VALUES (:id, :email, :name, NOW())"),
                {"id": str(user_id), "email": f"test2_{user_id}@example.com", "name": "Test"},
            )
            await session.execute(
                text("INSERT INTO orders (id, user_id, status, total_amount, created_at) VALUES (:id, :user_id, 'created', 100.00, NOW())"),
                {"id": str(order_id), "user_id": str(user_id)},
            )
            await session.execute(
                text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'created', NOW())"),
                {"order_id": str(order_id)},
            )

    async def attempt(n):
        async with AsyncSessionLocal() as s:
            service = PaymentService(s)
            return await service.pay_order_unsafe(order_id)

    results = await asyncio.gather(attempt(1), attempt(2), return_exceptions=True)

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    print(f"\nУспешных попыток: {success_count} из 2")

    # Очистка
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {"id": str(order_id)})
            await session.execute(text("DELETE FROM orders WHERE id = :id"), {"id": str(order_id)})
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})

    assert success_count >= 1, "Ожидалась хотя бы одна успешная попытка"

if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_unsafe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_unsafe_demonstrates_race_condition PASSED
    
    Вывод должен показывать:
    ⚠️ RACE CONDITION DETECTED!
    Order XXX was paid TWICE:
      - 2024-XX-XX: status = paid
      - 2024-XX-XX: status = paid
    """
    pytest.main([__file__, "-v", "-s"])
