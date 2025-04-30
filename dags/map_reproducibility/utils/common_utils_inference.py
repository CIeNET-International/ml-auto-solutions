# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import jsonlines

PROJECT = "supercomputer-testing"
BUCKET_NAME = "regression-testing-xlml"

def helm_apply_cmds_internal_run_inference(
    framework: str,
    hypercomputer: str,
    config_file,
    recipe_repo_root,
    values_file_path,
    docker_image,
    aotc: bool = False,
    cluster_name: str = "a3plus-benchmark",
    kueue_name: str = "a3-ultra",
    additional_cmds: str = "",
    test_run=False,
):
  gcs_cmd = ""
  if framework == "maxtext":
    gcs_cmd += f" --set volumes.gcsMounts[0].bucketName={BUCKET_NAME} "

  if hypercomputer == "a3ultra":
    if framework != "maxtext":
      gcs_cmd += f" --set queue={kueue_name} "
  else:
    gcs_cmd += f" --set workload.gcsBucketForDataCataPath={BUCKET_NAME} "

  cluster_cmd = ""
  if framework == "nemo" and hypercomputer == "a3ultra":
    cluster_cmd = f" --set clusterName={cluster_name} "

  run_name_cmd = ""
  if framework == "maxtext":
    run_name_cmd = " --set workload.run_name=$JOB_NAME "

  set_aotc = ""
  if aotc:
    set_aotc = " --set-string workload.aotc=true "

  if test_run:
    helm_template_path = f"/home/airflow/gcs/dags/dags/map_reproducibility/helm-charts/{hypercomputer}/{framework}-inference"
  else:
    helm_template_path = f"{recipe_repo_root}/src/helm-charts/{hypercomputer}/{framework}-inference"

  print(f"helm_template_path is {helm_template_path}")

  helm_cmds = (
      f" helm install -f {values_file_path} "
      "--namespace default "
      "--set namespace=default"
      f" --set-file {framework}_config"
      f"={config_file}"
      " --set workload.image"
      f"={docker_image} "
      f"{cluster_cmd} {run_name_cmd} {gcs_cmd} {set_aotc}"
      f"{additional_cmds}"
      # f" $JOB_NAME {recipe_repo_root}/src/helm-charts/{hypercomputer}/{framework}-training",
      f" $JOB_NAME {helm_template_path}",
  )
  print("*******helm cmd is*******")
  print(helm_cmds)
  return helm_cmds

def extract_and_write_to_jsonl_pattern(input_file, output_file):
  """
  Extracts AutoRegressive results from a text file using patterns
  and writes them to a JSONL file.

  Args:
      input_file (str): Path to the input text file.
      output_file (str): Path to the output JSONL file.
  """
  extraction_patterns = {
      "ar_step_average_time_ms": r"AR step average time: (\d+\.\d+) ms",
      "ar_step_average_time_per_seq_ms": r"AR step average time per seq: (\d+\.\d+) ms",
      "ar_global_batch_size": r"AR global batch size: (\d+)",
      "ar_throughput_tokens_per_second": r"AR throughput: (\d+\.\d+) tokens/second",
      "ar_memory_bandwidth_gb_per_second": r"AR memory bandwidth per device: (\d+\.\d+) GB/s",
  }

  results = dict()
  results["dimensions"] = dict()
  results["metrics"] = dict()
  try:
    with open(input_file, "r") as f:
      for line in f:
        line = line.strip()
        for key, pattern in extraction_patterns.items():
          match = re.search(pattern, line)
          if match:
            if "." in match.group(1):
              results["metrics"][key] = float(match.group(1))
            else:
              results["metrics"][key] = int(match.group(1))
            break  # Move to the next line once a match is found

    if results:
      with jsonlines.open(output_file, "w") as writter:
        writter.write(results)
      print(f"Extracted results written to {output_file}")
    else:
      print("No AutoRegressive results found in the input file.")

  except FileNotFoundError:
    print(f"Error: Input file '{input_file}' not found.")
  except Exception as e:
    print(f"An error occurred: {e}")
