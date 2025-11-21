import os

# Root project directory
root = r"D:\Quant Analytics App"

# Folder structure definition
folders = [
    "backend",
    "api",
    "api\\routes",
    "frontend",
    "frontend\\components",
    "frontend\\assets",
    "database",
    "logs",
    "architecture"
]

# Files to create inside each folder
files = {
    "backend": [
        "__init__.py",
        "websocket_ingest.py",
        "data_storage.py",
        "analytics_engine.py",
        "alert_system.py",
        "backtest_engine.py",
        "utils.py"
    ],
    "api": ["flask_server.py"],
    "api\\routes": ["analytics_routes.py", "alert_routes.py", "data_routes.py"],
    "frontend": ["streamlit_app.py"],
    "frontend\\components": [
        "price_chart.py",
        "spread_chart.py",
        "correlation_heatmap.py",
        "backtest_panel.py",
        "alert_panel.py"
    ],
    "frontend\\assets": ["dark_theme.css"],
    "database": [],  # ticks.db will be auto-created by code
    "logs": ["app.log"],
    "architecture": ["architecture_diagram.drawio", "architecture_diagram.png"]
}

# Base files
base_files = ["README.md", "requirements.txt", "app.py"]

def make_project_structure():
    print(f"Creating Quant Analytics App at: {root}\n")
    for folder in folders:
        path = os.path.join(root, folder)
        os.makedirs(path, exist_ok=True)
        print(f"📁 Folder created: {path}")
        # Create files in each folder
        for f in files.get(folder, []):
            file_path = os.path.join(path, f)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(f"# {f} - auto-generated placeholder\n")
                print(f"  📝 File created: {file_path}")

    # Create base files
    for base in base_files:
        file_path = os.path.join(root, base)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(f"# {base} - auto-generated placeholder\n")
            print(f"🧱 Base file created: {file_path}")

    print("\n✅ Project structure setup complete!")

if __name__ == "__main__":
    make_project_structure()
