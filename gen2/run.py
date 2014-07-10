#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have an agreement
# with Numenta, Inc., for a separate license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------
import os
import sys
import csv
import importlib
from optparse import OptionParser

from nupic.data.inference_shifter import InferenceShifter
from nupic.frameworks.opf.modelfactory import ModelFactory

import nupic_output


MODEL_PARAMS_DIR = "./model_params"
DEFAULT_MODEL_PARAMS_NAME = "1field_anomaly"
verbose = False


parser = OptionParser(
  usage="%prog <path/to/input/directory> [options]\n\nRun NuPIC on data "
        "generated from the 'convert_wav.py' script."
)

parser.add_option(
  "-m",
  "--model_params",
  dest="model_params_name",
  default=DEFAULT_MODEL_PARAMS_NAME,
  help="Name of the model params to use (without the '_model_params.py').")
parser.add_option(
  "-p",
  "--plot",
  action="store_true",
  default=False,
  dest="plot",
  help="Plots the output instead of writing to file."
)
parser.add_option(
  "-v",
  "--verbose",
  action="store_true",
  default=False,
  dest="verbose",
  help="Print debugging statements.")


def createModel(modelParams, bin):
  model = ModelFactory.create(modelParams)
  model.enableInference({"predictedField": bin})
  return model



def getModelParamsFromName(modelName, bin):
  importName = "model_params.%s_model_params" % (
    modelName.replace(" ", "_").replace("-", "_")
  )
  print "Importing model params from %s for bin %s" % (importName, bin)
  try:
    importedModelParams = importlib.import_module(importName).MODEL_PARAMS
  except ImportError:
    raise Exception("No model params exist for '%s'!" % modelName)
  # Replace the field name with the bin name
  encoder = importedModelParams['modelParams']['sensorParams']['encoders']['REPLACE_ME']
  encoder['fieldname'] = bin
  encoder['name'] = bin
  # del importedModelParams['modelParams']['sensorParams']['encoders']['REPLACE_ME']
  importedModelParams['modelParams']['sensorParams']['encoders'][bin] = encoder
  return importedModelParams



def runIoThroughNupic(input_path, output_path, model, model_name, bin, plot):
  with open(input_path, "rb") as input_file:
    csvReader = csv.reader(input_file)
    # skip header rows
    headers = csvReader.next()
    csvReader.next()
    csvReader.next()
    shifter = InferenceShifter()

    if plot:
      output = nupic_output.NuPICPlotOutput(model_name, bin)
    else:
      output = nupic_output.NuPICFileOutput(model_name, bin, path=output_path)

    counter = 0
    for row in csvReader:
      assert len(row) == len(headers)
      counter += 1
      if (counter % 100 == 0):
        print "Read %i lines..." % counter
      row = [float(row[0])] + [int(val) for val in row[1:]]
      input_row = dict(zip(headers, row))
      result = model.run(input_row)

      if plot:
        seconds = input_row["seconds"]
        actual = input_row[bin]
        shifter.shift(result)
        predicted = result.inferences["multiStepBestPredictions"][1]
        output.write([seconds], [actual], [predicted])
      else:
        output.write(input_row, result)

    output.close()



def runModels(input_path, model_params_name, plot):
  print "Creating models from %s using %s_model_params..." \
        % (input_path, model_params_name)

  for input_file in os.listdir(input_path):
    if verbose:
      print "Found input file %s" % input_file
    bin = os.path.splitext(input_file)[0]
    modelParams = getModelParamsFromName(model_params_name, bin)
    model = createModel(modelParams, bin)
    input_file_path = os.path.join(input_path, input_file)
    output_path = os.path.join(input_path, '../output')
    if not os.path.exists(output_path):
      os.makedirs(output_path)
    runIoThroughNupic(input_file_path, output_path, model, bin, bin, plot)



if __name__ == "__main__":
  (options, args) = parser.parse_args(sys.argv[1:])
  try:
    input_path = args.pop(0)
  except IndexError:
    parser.print_help(sys.stderr)
    sys.exit()

  verbose = options.verbose

  runModels(input_path, options.model_params_name, options.plot)
