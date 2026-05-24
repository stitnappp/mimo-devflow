from setuptools import setup, find_packages
setup(
    name="mimo-agent-mesh-e3dd66",
    version="0.1.0",
    description="MIMO Agent Mesh - Xiaomi MiMo API Orchestration",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["httpx", "pydantic", "rich", "asyncio"],
)
