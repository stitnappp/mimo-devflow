from setuptools import setup, find_packages
setup(
    name="mimo-devflow-o8k471",
    version="0.1.0",
    description="MIMO DevFlow Agent - Xiaomi MiMo API Orchestration",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["httpx", "pydantic", "rich", "asyncio"],
)
