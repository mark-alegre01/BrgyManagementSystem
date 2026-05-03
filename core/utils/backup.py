import os
import shutil
import tarfile
import json
import subprocess
from django.conf import settings
from django.utils.timezone import now

def get_backup_destinations():
    """Returns a list of potential backup destinations using robust detection."""
    destinations = []
    
    # 1. Local backup folder (always available)
    local_backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(local_backup_dir, exist_ok=True)
    
    # 2. Use lsblk -J to find removable drives
    try:
        output = subprocess.check_output(['lsblk', '-J', '-o', 'NAME,MOUNTPOINT,RM,TYPE,FSTYPE'], text=True)
        data = json.loads(output)
        
        def process_devices(devices):
            for dev in devices:
                # Check for removable drives (RM="1") that are disks or partitions
                is_removable = str(dev.get('rm', '0')) == '1' or str(dev.get('rm', '0')) == 'True'
                is_valid_type = dev.get('type') in ('part', 'disk')
                mountpoint = dev.get('mountpoint')
                name = dev.get('name')
                
                if is_removable and is_valid_type:
                    dest = {
                        'path': mountpoint if mountpoint and mountpoint != 'None' else None,
                        'name': name,
                        'device': f"/dev/{name}",
                        'is_mounted': bool(mountpoint and mountpoint != 'None'),
                        'is_external': True
                    }
                    # If mounted, verify write access
                    if dest['is_mounted'] and os.path.isdir(mountpoint) and os.access(mountpoint, os.W_OK):
                        # Avoid duplicates
                        if not any(d.get('path') == dest['path'] for d in destinations if isinstance(d, dict)):
                            destinations.append(dest)
                    elif not dest['is_mounted']:
                        # Add unmounted drives so the user can see they are detected
                        destinations.append(dest)
                
                # Recurse children if any
                if 'children' in dev:
                    process_devices(dev['children'])
                    
        if 'blockdevices' in data:
            process_devices(data['blockdevices'])
    except Exception:
        pass

    # 3. Fallback: Common mount points scan
    mount_bases = ['/media', '/mnt', '/run/media']
    extended_bases = set(mount_bases)
    for base in mount_bases:
        if os.path.exists(base):
            try:
                for entry in os.listdir(base):
                    full_path = os.path.join(base, entry)
                    if os.path.isdir(full_path):
                        extended_bases.add(full_path)
            except (PermissionError, OSError):
                continue
                
    for base in extended_bases:
        if os.path.exists(base):
            try:
                for entry in os.listdir(base):
                    full_path = os.path.join(base, entry)
                    if os.path.isdir(full_path) and os.access(full_path, os.W_OK):
                        dest = {
                            'path': os.path.abspath(full_path),
                            'name': entry,
                            'device': None,
                            'is_mounted': True,
                            'is_external': True
                        }
                        # Avoid duplicates
                        if not any(d.get('path') == dest['path'] for d in destinations if isinstance(d, dict)):
                            destinations.append(dest)
            except (PermissionError, OSError):
                continue
    
    # Final cleanup and local fallback addition
    final_destinations = []
    
    # Add local backup first
    final_destinations.append({
        'path': os.path.abspath(local_backup_dir),
        'name': 'backups',
        'device': None,
        'is_mounted': True,
        'is_external': False
    })
    
    for d in destinations:
        if not isinstance(d, dict): continue
        
        if d.get('path'):
            abs_path = os.path.abspath(d['path'])
            # Don't add if it's already the local backup folder or already in final
            if abs_path == os.path.abspath(local_backup_dir): continue
            if not any(fd.get('path') == abs_path for fd in final_destinations):
                d['path'] = abs_path
                final_destinations.append(d)
        elif not d.get('is_mounted'):
             # Keep unmounted ones, avoiding device duplicates
             if not any(fd.get('device') == d.get('device') for fd in final_destinations):
                final_destinations.append(d)
            
    return final_destinations

def perform_backup(target_base=None):
    """Performs the backup of the database and media files."""
    timestamp = now().strftime('%Y%m%d_%H%M%S')
    backup_folder_name = f"backup_{timestamp}"
    
    if not target_base:
        all_dests = get_backup_destinations()
        mounted_dests = [d for d in all_dests if d.get('is_mounted')]
        if not mounted_dests:
            return False, "No writeable backup destinations found."
        
        # Prefer external drives
        target_base = mounted_dests[0]['path']
        for d in mounted_dests:
            if d.get('is_external'):
                target_base = d['path']
                break
            
    target_dir = os.path.join(target_base, 'BrgySystemBackups', backup_folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        # 1. Backup SQLite database
        db_path = settings.DATABASES['default']['NAME']
        if os.path.exists(db_path):
            shutil.copy2(db_path, os.path.join(target_dir, 'db.sqlite3'))
        
        # 2. Backup Media files
        media_root = settings.MEDIA_ROOT
        if os.path.exists(media_root) and os.listdir(media_root):
            media_tar = os.path.join(target_dir, 'media.tar.gz')
            with tarfile.open(media_tar, "w:gz") as tar:
                tar.add(media_root, arcname=os.path.basename(media_root))
        
        # 3. Create a metadata file
        with open(os.path.join(target_dir, 'metadata.txt'), 'w') as f:
            f.write(f"Backup created on: {now().isoformat()}\n")
            f.write(f"Source: {settings.BASE_DIR}\n")
            
        return True, f"Backup successfully created at: {target_dir}"
    except Exception as e:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        return False, f"Backup failed: {str(e)}"

def create_backup_archive():
    """Creates a temporary ZIP archive containing the database and media files."""
    import tempfile
    import zipfile
    
    timestamp = now().strftime('%Y%m%d_%H%M%S')
    filename = f"BrgySystem_Backup_{timestamp}.zip"
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, filename)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add database
            db_path = settings.DATABASES['default']['NAME']
            if os.path.exists(db_path):
                zipf.write(db_path, 'db.sqlite3')
            
            # 2. Add media files
            media_root = settings.MEDIA_ROOT
            if os.path.exists(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join('media', os.path.relpath(file_path, media_root))
                        zipf.write(file_path, arcname)
            
            # 3. Add metadata
            metadata_content = f"Backup created on: {now().isoformat()}\nSource: {settings.BASE_DIR}\n"
            zipf.writestr('metadata.txt', metadata_content)
            
        return zip_path
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise e
