import requests
import os
import shutil
import zipfile


def clean_install():
    folder = os.path.dirname(os.path.abspath(__file__))
    temp_folder = folder + '/Temp'
    if not os.path.exists(temp_folder):
        os.mkdir(temp_folder)
    sample_path = temp_folder + "/update_python_sim.sample"
    sample_open = open(sample_path, 'r')
    lines = sample_open.read().split('\n')
    sample_open.close()
    f_path = temp_folder + "/update_python_sim.bat"
    f_open = open(f_path, 'w')
    for line in lines:
        line = line.replace('ROOT_FOLDER', folder)
        f_open.write(line + '\n')
    f_open.close()
    os.system(f_path)


def download_python_sim():
    folder = os.path.dirname(os.path.abspath(__file__))
    f_path = folder + '/Readme.txt'
    f_open = open(f_path, 'r')
    lines = f_open.read().splitlines()
    prefix_version = 'Python SNMP N-Simulator ver '
    version = lines[0].replace(prefix_version, '')
    link = 'https://www.dropbox.com/s/rntyaxaaxn03oai/Readme.txt?dl=1'
    f_source = requests.get(link)
    f_text = f_source.text.split('\n')
    f_open.close()
    if f_text:
        for line in f_text:
            if prefix_version in line:
                latest_version = line.replace(prefix_version, '')
                if float(latest_version) > float(version):
                    temp_folder = folder + '/Temp'
                    if not os.path.exists(temp_folder):
                        os.mkdir(temp_folder)
                    zf_path = temp_folder + '/_Backup_Python_Sim.zip'
                    zf = zipfile.ZipFile(zf_path, 'w')
                    for dir_name, sub_dirs, files in os.walk(folder):
                        if dir_name != 'Temp':
                            zf.write(dir_name)
                        for filename in files:
                            file_join = os.path.join(dir_name, filename)
                            if 'Temp' not in file_join:
                                zf.write(file_join)
                    zf.close()
                    download_link = 'https://www.dropbox.com/sh/znpy5xjvsa4ehya/AAC2_2Di9NzpR5HaABhMOfLia?dl=1'
                    download_archive = requests.get(download_link, stream=True)
                    archive_path = temp_folder + '/Python_Sim.zip'
                    with open(archive_path, 'wb') as archive:
                        shutil.copyfileobj(download_archive.raw, archive)
                    extract_folder = temp_folder + '/Python_Sim'
                    zip_ref = zipfile.ZipFile(archive_path, 'r')
                    zip_ref.extractall(extract_folder)
                    zip_ref.close()
                    break


if __name__ == "__main__":
    download_python_sim()
    clean_install()
