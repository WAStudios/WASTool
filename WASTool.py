import os
import subprocess
import yaml
import requests
import shutil
import stat

PKGMETA_URL = "https://raw.githubusercontent.com/WeakAuras/WeakAuras2/main/.pkgmeta"
WASLIBS_REPO_PATH = "./WASLibs"
WASLIBS_REMOTE = "git@github.com:WAStudios/WASLibs.git"  # Use SSH for automation

def fetch_pkgmeta():
    print(f"Fetching .pkgmeta from {PKGMETA_URL}")
    response = requests.get(PKGMETA_URL)
    if response.status_code == 200:
        pkgmeta_temp = "pkgmeta_temp.yml"
        with open(pkgmeta_temp, "w") as f:
            f.write(response.text)
        print(".pkgmeta fetched successfully.")
        return pkgmeta_temp
    else:
        raise Exception(f"Failed to fetch .pkgmeta: {response.status_code}")

def valid_refs(target_path):
    result = subprocess.run(
        ["git", "-C", target_path, "ls-remote", "--heads", "--tags", "origin"],
        capture_output=True, text=True, check=True
    )
    refs = [line.split()[1].replace('refs/heads/', '').replace('refs/tags/', '') for line in result.stdout.splitlines()]
    return refs

def handle_remove_readonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == 5:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def sync_libraries(pkgmeta_path, libs_dir):
    with open(pkgmeta_path, "r") as f:
        pkgmeta_data = yaml.safe_load(f)

    externals = pkgmeta_data.get("externals", {})
    print(f"Found {len(externals)} externals in .pkgmeta")

    for path, data in externals.items():
        target_path = os.path.join(libs_dir, os.path.basename(path))
        if isinstance(data, str):
            url = data
            branch_or_tag = None
        elif isinstance(data, dict):
            url = data.get("url")
            branch_or_tag = data.get("tag") or data.get("commit")
        else:
            print(f"Unknown format for {path}, skipping.")
            continue

        if os.path.exists(target_path):
            if os.path.exists(os.path.join(target_path, ".git")):
                try:
                    refs = valid_refs(target_path)
                    result = subprocess.run(["git", "-C", target_path, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
                    current_branch = result.stdout.strip()

                    if current_branch == "HEAD":
                        subprocess.run(["git", "-C", target_path, "fetch", "-q"], check=True)
                        if branch_or_tag in refs:
                            subprocess.run(["git", "-C", target_path, "checkout", branch_or_tag, "-q"], check=True)
                        else:
                            fallback = "master" if "master" in refs else "main"
                            subprocess.run(["git", "-C", target_path, "reset", "--hard", f"origin/{fallback}", "-q"], check=True)
                            subprocess.run(["git", "-C", target_path, "checkout", fallback, "-q"], check=True)
                    else:
                        subprocess.run(["git", "-C", target_path, "pull", "-q"], check=True)

                except subprocess.CalledProcessError as e:
                    print(f"Git operation failed for {target_path}: {e}")
                continue
            elif os.path.exists(os.path.join(target_path, ".svn")):
                subprocess.run(["svn", "update", target_path, "--quiet"], check=True)
                continue

        if "townlong-yak.com" in url or url.endswith(".git") or "github.com" in url:
            try:
                subprocess.run(["git", "clone", "-q", url, target_path], check=True)
                if branch_or_tag:
                    subprocess.run(["git", "-C", target_path, "checkout", branch_or_tag, "-q"], check=True)
                if os.path.exists(os.path.join(target_path, ".git")):
                    shutil.rmtree(os.path.join(target_path, ".git"), onerror=handle_remove_readonly)
            except subprocess.CalledProcessError as e:
                print(f"Git clone failed for {url}: {e}")
        else:
            try:
                subprocess.run(["svn", "checkout", url, target_path, "--quiet"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"SVN checkout failed for {url}: {e}")

    print("All libraries fetched or updated successfully.")

def commit_and_push_waslibs():
    try:
        subprocess.run(["git", "-C", WASLIBS_REPO_PATH, "add", "."], check=True)
        subprocess.run(["git", "-C", WASLIBS_REPO_PATH, "commit", "-m", "Update libraries from latest .pkgmeta"], check=True)
        subprocess.run(["git", "-C", WASLIBS_REPO_PATH, "push"], check=True)
        print("WASLibs repository updated and pushed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to update WASLibs repository: {e}")
        return False

def main():
    pkgmeta_file = fetch_pkgmeta()

    if not os.path.exists(WASLIBS_REPO_PATH):
        subprocess.run(["git", "clone", WASLIBS_REMOTE, WASLIBS_REPO_PATH], check=True)

    subprocess.run(["git", "-C", WASLIBS_REPO_PATH, "remote", "set-url", "origin", WASLIBS_REMOTE], check=True)

    libs_dir = os.path.join(WASLIBS_REPO_PATH, "libs")
    if not os.path.exists(libs_dir):
        os.makedirs(libs_dir)

    sync_libraries(pkgmeta_file, libs_dir)

    success = commit_and_push_waslibs()

    os.remove(pkgmeta_file)

    if success and os.path.exists(WASLIBS_REPO_PATH):
        print("Cleaning up local WASLibs directory...")
        shutil.rmtree(WASLIBS_REPO_PATH, onerror=handle_remove_readonly)
        print("Cleanup complete.")

if __name__ == "__main__":
    main()