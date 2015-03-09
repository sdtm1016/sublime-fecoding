import sublime, sublime_plugin
import os, sys, subprocess, codecs, webbrowser
import json

try:
  import commands
except ImportError:
  pass

PLUGIN_FOLDER  = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE  = "Fecoding.sublime-settings"
OUTPUT_SPLITER = b"*** Fecoding output json ***"

class FecodingEventListeners(sublime_plugin.EventListener):
  @staticmethod
  def on_pre_save(view):
    if PluginUtils.get_pref("do_on_save"):
      view.run_command("fecoding")

class FecodingCommand(sublime_plugin.TextCommand):
  def run(self, edit, action='save', actionArg=''):

    # Save the current viewport position to scroll to it after formatting.
    previous_selection = list(self.view.sel()) # Copy.
    previous_position = self.view.viewport_position()

    # Save the already folded code to refold it after formatting.
    # Backup of folded code is taken instead of regions because the start and end pos
    # of folded regions will change once formatted.
    folded_regions_content = [self.view.substr(r) for r in self.view.folded_regions()]

    # Get the current text in the buffer and save it in a temporary file.
    # This allows for scratch buffers and dirty files to be linted as well.
    entire_buffer_region = sublime.Region(0, self.view.size())
    text_selection_region = self.view.sel()[0]

    # Active Selection Area.
    work_only_selection = False
    plugins = PluginUtils.get_pref("plugins")
    if plugins:
      plugin = plugins.get(action)
      if plugin:
        do_only_selection = plugin.get('do_only_selection')
        if do_only_selection:
          if text_selection_region.empty():
            # not select any code.
            return
          else:
            work_only_selection = True

    if work_only_selection:
      temp_file_path, buffer_text = self.save_buffer_to_temp_file(text_selection_region)
    else:
      temp_file_path, buffer_text = self.save_buffer_to_temp_file(entire_buffer_region)

    output = self.run_script_on_file(action, actionArg, temp_file_path)

    os.remove(temp_file_path)
    output = self.get_output_data(output)

    # http://www.sublimetext.com/docs/3/api_reference.html
    # http://my.oschina.net/goodtemper/blog/295243
    #try:
    output = json.loads(output or '{}')

    output_flag = output.get('flag')
    if not output_flag is None:
      output_action = output.get('action')
      output_content = output.get('content')
      output_message = output.get('message')
      if output_action:
        # show message
        if output_action == 'show_message' and output_message:
          sublime.message_dialog(output_message)
        # status message
        if output_action == 'status_message' and output_message:
          sublime.status_message(output_message)
        # open file
        if output_action == 'open_file' and output_content:
          self.view.window().open_file(output_content)

        # update view
        if output_action == 'update_view' and output_content:
          # Replace the text only if it's different.
          if output != buffer_text:
            if work_only_selection:
              self.view.replace(edit, text_selection_region, output_content)
            else:
              self.view.replace(edit, entire_buffer_region, output_content)

            self.refold_folded_regions(folded_regions_content, output_content)
            self.view.set_viewport_position((0, 0), False)
            self.view.set_viewport_position(previous_position, False)
            self.view.sel().clear()

            # Restore the previous selection if formatting wasn't performed only for it.
            if not work_only_selection:
              for region in previous_selection:
                self.view.sel().add(region)
      else:
        print('invalid output action.')
    else:
      print('invalid output flag.')

  def get_output_data(self, output):
    index = output.find(OUTPUT_SPLITER)
    return output[index + len(OUTPUT_SPLITER):].decode("utf-8")

  def save_buffer_to_temp_file(self, region):
    buffer_text = self.view.substr(region)
    temp_file_name = ".__fecodingtemp__"
    temp_file_path = PLUGIN_FOLDER + "/" + temp_file_name
    f = codecs.open(temp_file_path, mode="w", encoding="utf-8")
    f.write(buffer_text)
    f.close()
    return temp_file_path, buffer_text

  def refold_folded_regions(self, folded_regions_content, entire_file_contents):
    self.view.unfold(sublime.Region(0, len(entire_file_contents)))
    region_end = 0

    for content in folded_regions_content:
      region_start = entire_file_contents.index(content, region_end)
      if region_start > -1:
        region_end = region_start + len(content)
        self.view.fold(sublime.Region(region_start, region_end))

  def run_script_on_file(self, action, actionArg, temp_file_path):
    try:
      node_path = PluginUtils.get_node_path()
      script_path = PLUGIN_FOLDER + '/scripts/bin.js'
      config_path = PLUGIN_FOLDER + '/' + SETTINGS_FILE
      # get file path
      file_path = self.view.file_name()
      # set cmd params
      cmd = [ node_path, script_path, \
              action, \
              "--args", actionArg, \
              "--confpath", config_path, \
              "--filepath", file_path or "?", \
              "--temppath", temp_file_path \
            ]

      debug = PluginUtils.get_pref("debug")
      # log
      if debug:
        print('fecoding command "'+ action + '"')
        print('node lib/fecoding.js '+ action + ' --args "'+ actionArg + '" --confpath "'+ config_path +'" --filepath "'+ (file_path or '?') + '" --temppath "'+ temp_file_path +'"')

      output = PluginUtils.get_output(cmd)

      if debug:
        print(output)

      # Make sure the correct/expected output is retrieved.
      if output.find(OUTPUT_SPLITER) != -1:
        return output

      msg = "Command " + '" "'.join(cmd) + " created invalid output."
      print(output)
      raise Exception(msg)

    except:
      # Something bad happened.
      print("Unexpected error({0}): {1}".format(sys.exc_info()[0], sys.exc_info()[1]))

      # Usually, it's just node.js not being found. Try to alleviate the issue.
      msg = "Node.js was not found in the default path. Please specify the location."
      if not sublime.ok_cancel_dialog(msg):
        msg = "You won't be able to use this plugin without specifying the path to node.js."
        sublime.error_message(msg)
      else:
        self.view.window().open_file(PLUGIN_FOLDER + '/' + SETTINGS_FILE)

class PluginUtils:
  @staticmethod
  def get_pref(key):
    return sublime.load_settings(SETTINGS_FILE).get(key)

  @staticmethod
  def exists_in_path(cmd):
    # Can't search the path if a directory is specified.
    assert not os.path.dirname(cmd)
    path = os.environ.get("PATH", "").split(os.pathsep)
    extensions = os.environ.get("PATHEXT", "").split(os.pathsep)

    # For each directory in PATH, check if it contains the specified binary.
    for directory in path:
      base = os.path.join(directory, cmd)
      options = [base] + [(base + ext) for ext in extensions]
      for filename in options:
        if os.path.exists(filename):
          return True

    return False

  @staticmethod
  def get_node_path():
    platform = sublime.platform()
    node = PluginUtils.get_pref("node_path").get(platform)
    print("Using node.js path on '" + platform + "': " + node)
    return node

  @staticmethod
  def get_output(cmd):
    if int(sublime.version()) < 3000:
      if sublime.platform() != "windows":
        # Handle Linux and OS X in Python 2.
        run = '"' + '" "'.join(cmd) + '"'
        return commands.getoutput(run)
      else:
        # Handle Windows in Python 2.
        # Prevent console window from showing.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, startupinfo=startupinfo).communicate()[0]
    else:
      # Handle all OS in Python 3.
      run = '"' + '" "'.join(cmd) + '"'
      return subprocess.check_output(run, stderr=subprocess.STDOUT, shell=True, env=os.environ)
