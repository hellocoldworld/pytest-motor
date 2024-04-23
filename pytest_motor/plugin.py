"""A pytest plugin which helps test applications using Motor."""
import asyncio
import os
import socket
import tempfile
from pathlib import Path
from typing import AsyncIterator, Iterator, List

import pymongo
import pytest
import pytest_asyncio
from _pytest.config import Config as PytestConfig
from motor.motor_asyncio import AsyncIOMotorClient

from pytest_motor.mongod_binary import MongodBinary

AS_REPLICA_SET = bool(os.environ.get("AS_REPLICA_SET", True))


@pytest.fixture(scope='function')
def event_loop() -> asyncio.AbstractEventLoop:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def root_directory(pytestconfig: PytestConfig) -> Path:
    """Return the root path of pytest."""
    return pytestconfig.rootpath


@pytest.fixture(scope="function")
async def mongod_binary(root_directory: Path) -> Path:
    # pylint: disable=redefined-outer-name
    """Return a path to a mongod binary."""
    destination: Path = root_directory / ".mongod"
    binary = MongodBinary(destination=destination)
    if not binary.exists:
        await binary.download_and_unpack()
    return binary.path


@pytest.fixture(scope="function")
def new_port() -> int:
    """Return an unused port for mongod to run on."""
    port: int = 27017
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as opened_socket:
        opened_socket.bind(("127.0.0.1", 0))  # system will automaticly assign port
        port = opened_socket.getsockname()[1]
    return port


@pytest.fixture(scope="function")
def database_path() -> Iterator[str]:
    """Yield a database path for a mongod process to store data."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture(scope="function")
async def mongod_socket(new_port: int, database_path: Path,
                        mongod_binary: Path) -> AsyncIterator[str]:
    # pylint: disable=redefined-outer-name
    """Yield a mongod."""
    # yapf: disable
    arguments: List[str] = [
        str(mongod_binary),
        '--port', str(new_port),
        '--storageEngine', 'ephemeralForTest',
        '--logpath', '/dev/null',
        '--dbpath', str(database_path)
    ]
    arguments.append("--replSet")
    arguments.append("rs0")
    # yapf: enable

    mongod = await asyncio.create_subprocess_exec(*arguments)
    db_uri = f"localhost:{new_port}"

    if AS_REPLICA_SET:
        conn = pymongo.MongoClient(port=new_port, directConnection=True)

        conn.admin.command({
            "replSetInitiate": {
                "_id": "rs0",
                "members": [{
                    "_id": 0,
                    "host": f"localhost:{new_port}"
                }],
            }
        })
        conn.admin.command({"replSetGetConfig": 1})

    # mongodb binds to localhost by default
    yield db_uri

    try:
        mongod.terminate()
    except ProcessLookupError:  # pragma: no cover
        pass


@pytest.fixture(scope="function")
def __motor_client(mongod_socket: str) -> AsyncIterator[AsyncIOMotorClient]:
    # pylint: disable=redefined-outer-name
    """Yield a Motor client."""
    conn = pymongo.MongoClient(host=mongod_socket, replicaSet="rs0", directConnection=True)
    conn.admin.command({
        "setDefaultRWConcern": 1,
        "defaultWriteConcern": {
            "w": 1,
            "wtimeout": 2000
        },
        "writeConcern": {
            "w": 0
        },
    })

    connection_string = f"mongodb://{mongod_socket}"

    motor_client_: AsyncIOMotorClient = AsyncIOMotorClient(connection_string,
                                                           serverSelectionTimeoutMS=3000,
                                                           retryWrites=False)

    yield motor_client_

    motor_client_.close()


@pytest.fixture(scope="function")
async def motor_client(
        __motor_client: AsyncIterator[AsyncIOMotorClient],
        event_loop: asyncio.AbstractEventLoop,  # pylint: disable=unused-argument
) -> AsyncIterator[AsyncIOMotorClient]:
    # pylint: disable=redefined-outer-name
    """Yield a Motor client."""
    yield __motor_client

    dbs = await __motor_client.list_database_names()

    for db in dbs:
        if db not in ["config", "admin", "local"]:
            collections = await __motor_client[db].list_collections()
            for collection in collections:
                print(collection)
                await __motor_client[db].drop_collection(collection["name"])
