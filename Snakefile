import sys
import os

sys.path.append("./scripts")

configfile: "config.yaml"
configfile: "datasets/dataset_config.yaml"

CYCLEGAN_PARENT_FOLDER = "cycle"
CYCLEGAN_NAME_FOLDER = "pytorch-CycleGAN-and-pix2pix"
CYCLEGAN_FULL_PATH = os.path.abspath(CYCLEGAN_PARENT_FOLDER + "/" + CYCLEGAN_NAME_FOLDER)

wildcard_constraints:
    preload_dataset= "|".join(config["datasets"].keys()),
    general_dataset="[-+a-zA-Z0-9\.]*",

# rule to setup the cyclegan repo
rule setup_cyclegan:
    output: directory(CYCLEGAN_FULL_PATH)
    log: "logs/setup_cyclegan.log"
    run:
        shell("mkdir -p {output} > {log}")
        shell("git clone https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix {output} > {log}")
        shell("pip install -r {output}/requirements.txt > {log}")

# Rule to download data from google drive
rule download_dataset_gdrive:
    output: directory("datasets/{preload_dataset}")
    message:
        """
        Downloading {wildcards.preload_dataset}
        This implies that the users are accepting the data licencing by authors
        """
    run:
        dataset_name = wildcards["preload_dataset"]
        shell(
            "gdrive download --path " + os.path.dirname(output[0])
            + " --force " + config["datasets"][dataset_name]["gdrive"]
        )
        # name of the file to unzip
        import zipfile
        with zipfile.ZipFile(output[0] + ".zip", "r") as zipObj:
            # Extract all the contents of zip file in current directory
            zipObj.extractall(os.path.dirname(output[0]))
        os.remove(output[0] + ".zip")


rule cycle_train:
    input:
        cyclegan_dir=directory(CYCLEGAN_FULL_PATH),
        training_dataset_A=directory("datasets/{general_dataset}"),
        training_dataset_B=directory("datasets/{general_dataset}"),
    output: directory("datasets/cycletrain{general_dataset}")
    run:
        shell(
            "python {input.cyclegan_dir}/train.py"
            + " --dataroot " + os.path.abspath(input["training_dataset"])
            #+ " --results_dir {output}"
            #+ " --name " + wildcards["general_dataset"]
            + " --name {wildcards.general_dataset}"
            + " --model cycle_gan"
        )


rule cycle_test:
    input:
        cyclegan_dir=directory(CYCLEGAN_FULL_PATH),
        training_dataset=directory("datasets/{general_dataset}"),
    output: directory("datasets/cycletest{general_dataset}")
    run:
        shell(
            "python " + os.path.join(input["cyclegan_dir"], "train.py")
            + " --dataroot " + os.path.abspath(input["training_dataset"])
            + " --results_dir {output}"
            + " --name {wildcards.general_dataset}"
            + " --no_dropout --model cycle_gan --direction BtoA"
        )
