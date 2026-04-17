import pytest
from neo4j.exceptions import AuthError, ServiceUnavailable
from app.db.neo4j import get_driver, close_driver

def test_neo4j_connection():
    """测试 Neo4j 连接"""
    driver = get_driver()
    assert driver is not None

    # 验证连接
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            assert result.single()["num"] == 1
    except (AuthError, ServiceUnavailable) as e:
        pytest.skip(f"Neo4j not available or misconfigured: {e}")

    close_driver()
