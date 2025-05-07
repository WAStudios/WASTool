import os
import subprocess
import requests
import shutil
import yaml

WASLIBS_REPO_URL = "git@github.com:WAStudios/WASLibs.git"
WASLIBS_REPO_PATH = "./WASLibs"
PKGMETA_URL = "https://raw.githubusercontent.com/WeakAuras/WeakAuras2/main/.pkgmeta"

def fetch_pkgmeta():
    response = requests.get(PKGMETA_URL)
    response.raise_for_status()
    with open("pkgmeta_temp.yml", "w", encoding='utf-8') as f:
        f.write(response.text)
    return "pkgmeta_temp.yml"

def handle_remove_readonly(func, path, exc_info):
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup_previous():
    if os.path.exists(WASLIBS_REPO_PATH):
        print("Removing existing WASLibs directory before fresh run...")
        shutil.rmtree(WASLIBS_REPO_PATH, onerror=handle_remove_readonly)
        print("Previous WASLibs directory removed.")
    os.makedirs(WASLIBS_REPO_PATH)

def sync_libraries(pkgmeta_file):
    with open(pkgmeta_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    externals = data.get('externals', {})
    print(f"Found {len(externals)} externals in .pkgmeta")

    for path, repo_info in externals.items():
        target_path = os.path.join(WASLIBS_REPO_PATH, os.path.basename(path).replace('/', os.sep))
        repo_url = repo_info.get('url') if isinstance(repo_info, dict) else repo_info
        tag = repo_info.get('tag') if isinstance(repo_info, dict) else None

        if os.path.exists(target_path):
            print(f"Removing existing {target_path} before fresh clone...")
            shutil.rmtree(target_path, onerror=handle_remove_readonly)

        if repo_url.startswith("https://repos.curseforge.com") or repo_url.startswith("https://repos.wowace.com"):
            print(f"Using SVN to checkout {repo_url} into {target_path}")
            subprocess.run(['svn', 'checkout', repo_url, target_path], check=True)
        elif "townlong-yak.com" in repo_url:
            print(f"Using Git to clone {repo_url} into {target_path} (no depth, special case)")
            subprocess.run(['git', 'clone', repo_url, target_path], check=True)
        else:
            print(f"Using Git to clone {repo_url} into {target_path}")
            subprocess.run(['git', 'clone', '--depth', '1', repo_url, target_path], check=True)
            if tag:
                print(f"Fetching tags for {repo_url}...")
                subprocess.run(['git', '-C', target_path, 'fetch', '--tags'], check=True)
                print(f"Checking out tag {tag} in {target_path}")
                subprocess.run(['git', '-C', target_path, 'checkout', tag], check=True)

        # Clean up .git folders
        git_dir = os.path.join(target_path, '.git')
        if os.path.exists(git_dir):
            print(f"Removing embedded .git repository in {target_path}")
            shutil.rmtree(git_dir, onerror=handle_remove_readonly)

    print("All libraries fetched or updated successfully.")


def inject_manual_ace3_libs():
    print("Cloning Ace3 libraries manually...")

    ACE3_REPO = "https://github.com/hurricup/WoW-Ace3.git"
    CLONE_TEMP = "./Ace3_TEMP"
    TARGET = WASLIBS_REPO_PATH

    if os.path.exists(CLONE_TEMP):
        shutil.rmtree(CLONE_TEMP, onerror=handle_remove_readonly)

    print(f"Cloning {ACE3_REPO} into {CLONE_TEMP}...")
    subprocess.run(['git', 'clone', '--depth', '1', ACE3_REPO, CLONE_TEMP], check=True)

    for lib in ["AceAddon-3.0", "AceTimer-3.0", "CallbackHandler-1.0"]:
        src = os.path.join(CLONE_TEMP, lib)
        dst = os.path.join(TARGET, lib)
        if os.path.exists(dst):
            shutil.rmtree(dst, onerror=handle_remove_readonly)
        shutil.copytree(src, dst)
        print(f"✔ Injected {lib}")

    print("Cleaning up Ace3_TEMP clone...")
    shutil.rmtree(CLONE_TEMP, onerror=handle_remove_readonly)

def stage_commit_push():
    print("Initializing Git in WASLibs directory...")
    subprocess.run(['git', '-C', WASLIBS_REPO_PATH, 'init', '-b', 'main'], check=True)  # <-- set branch explicitly
    subprocess.run(['git', '-C', WASLIBS_REPO_PATH, 'remote', 'add', 'origin', WASLIBS_REPO_URL], check=True)
    print("Staging all files for commit...")
    subprocess.run(['git', '-C', WASLIBS_REPO_PATH, 'add', '.'], check=True)
    print("Committing changes...")
    try:
        subprocess.run(['git', '-C', WASLIBS_REPO_PATH, 'commit', '-m', 'Update libraries from latest .pkgmeta'], check=True)
        print("Pushing changes to remote...")
        subprocess.run(['git', '-C', WASLIBS_REPO_PATH, 'push', 'origin', 'main', '--force'], check=True)
        print("WASLibs repository updated and pushed successfully.")
    except subprocess.CalledProcessError:
        print("No changes to commit.")

def cleanup_temp():
    print("Cleaning up temporary files...")
    if os.path.exists("pkgmeta_temp.yml"):
        os.remove("pkgmeta_temp.yml")
    print("Cleanup complete.")

def main():
    cleanup_previous()
    pkgmeta = fetch_pkgmeta()
    sync_libraries(pkgmeta)
    inject_manual_ace3_libs()
    stage_commit_push()
    cleanup_temp()

if __name__ == "__main__":
    main()