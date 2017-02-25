#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015-2017 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not, see
# <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------------------------------------

"""YAML parser."""

import datetime
import io
import re

import yaml


##############################################################################################################

def parse_file(file_path):
   """Loads and parses a YAML file.

   str file_path
      Path to the YAML file.
   object return
      Python object corresponding to the contents of the file.
   """

   return Parser().parse_file(file_path)

def parse_string(s):
   """Loads and parses a string containing YAML.

   str s
      YAML source.
   object return
      Python object corresponding to the contents of the string.
   """

   return Parser().parse_string(s)

##############################################################################################################

class SyntaxError(Exception):
   """Indicates a syntactical or semantical error in a YAML source."""

   pass

##############################################################################################################

class TagKindMismatchError(SyntaxError):
   """Raised when a tag is applied to a YAML object of a kind not suitable to construct the tag."""

   pass

##############################################################################################################

_SCALAR_ALL       = 0b11111
_SCALAR_BOOL      = 0b00001
_SCALAR_FLOAT     = 0b00010
_SCALAR_INT       = 0b00100
_SCALAR_NULL      = 0b01000
_SCALAR_TIMESTAMP = 0b10000

def _make_values_int(kwargs):
   """Converts the values of its argument into int instances.

   dict(str: str) kwargs
      Dictionary containing string values to convert. Will be modified in place.
   dict(str: int) return
      kwargs, after it’s been modified.
   """

   ret = {}
   for key, value in kwargs.items():
      if value:
         ret[key] = int(value, 10)
   return ret

def _timestamp_to_datetime(**kwargs):
   """Constructs a datetime.datetime object by tweaking the arguments provided.

   dict(str: str) **kwargs
      Values parsed from the regular expression matching a YAML timestamp.
   datetime.datetime return
      Object containing the timestamp.
   """

   # Convert the generic “fraction” part into “microsecond”. This needs to be done while it’s still a string,
   # otherwise we won’t be able to tell the difference between “001” (1 ms) and “000001” (1 µs).
   fraction = kwargs.pop('fraction', None)
   if fraction:
      if len(fraction) == 6:
         # Already microseconds.
         microsecs = fraction
      elif len(fraction) < 6:
         # Too few digits; add some padding to multiply by the appropriate power of 10.
         microsecs = fraction.ljust(6, '0')
      else:
         # Too many digits; drop the excess.
         microsecs = fraction[0:6]
      kwargs['microsecond'] = microsecs
   tz = kwargs.pop('tz', None)

   kwargs = _make_values_int(kwargs)

   tz_hour = kwargs.pop('tzhour', 0)
   tz_minute = kwargs.pop('tzminute', 0)
   if tz == 'Z':
      kwargs['tzinfo'] = yaml.TimestampTZInfo('UTC', 0, 0)
   elif tz:
      kwargs['tzinfo'] = yaml.TimestampTZInfo(tz, tz_hour, tz_minute)

   return datetime.datetime(**kwargs)

class Parser(object):
   """YAML parser. Only accepts a small subset of YAML 1.2 (sequences, maps, scalars, comments).

   This implementation supports local tags (!tag_name); new local tags can be added by deriving a parser class
   from yaml.Parser, and then using the decorator @DerivedParser.local_tag('tag_name', yaml.Kind.SCALAR) or by
   calling DerivedParser.register_local_tag('tag_name', yaml.Kind.SCALAR, constructor).
   """

   # Built-in tags.
   _builtin_tags = {
      'bool'     : (yaml.Kind.SCALAR,   lambda yp, s: yp._construct_builtin_tag(_SCALAR_BOOL,  'bool',  s)),
      'float'    : (yaml.Kind.SCALAR,   lambda yp, s: yp._construct_builtin_tag(_SCALAR_FLOAT, 'float', s)),
      'int'      : (yaml.Kind.SCALAR,   lambda yp, s: yp._construct_builtin_tag(_SCALAR_INT,   'int',   s)),
      'map'      : (yaml.Kind.MAPPING,  lambda yp, dict: dict),
      'null'     : (yaml.Kind.SCALAR,   lambda yp, s: None),
      'seq'      : (yaml.Kind.SEQUENCE, lambda yp, list: list),
      'str'      : (yaml.Kind.SCALAR,   lambda yp, s: s),
      'timestamp': (yaml.Kind.SCALAR,   lambda yp, s: yp._construct_builtin_tag(_SCALAR_TIMESTAMP, 'timestamp', s)),
   }
   # Matches a comment.
   _comment_re = re.compile(r'[\t ]*#.*$')
   # Matches a document start mark.
   _doc_start_re = re.compile(r'^---(?: +|$)')
   # Matches trailing horizontal whitespace.
   _horizontal_ws_re = re.compile(r'[\t ]*$')
   # Matches leading horizontal whitespace.
   _indent_re = re.compile(r'^[\t ]*')
   # Stores local tags for each Parser subclass.
   _local_tags_by_parser_type = {}
   # Matches a mapping key and the whitespace around it.
   _mapping_key_re = re.compile(r'^(?P<key>[^:]+?) *:(?: +|$)')
   # Matchers and convertors for stock scalar types (see YAML 1.2 § 10.3.2. “Tag Resolution”).
   _scalar_tag_conversions = (
      (_SCALAR_NULL, re.compile(r'^(?:|~|NULL|[Nn]ull)$'), None),

      (_SCALAR_BOOL, re.compile(r'^(?:TRUE|[Tt]rue)$'  ), True),
      (_SCALAR_BOOL, re.compile(r'^(?:FALSE|[Ff]alse)$'), False),

      (_SCALAR_INT, re.compile(r'^(?P<s>[-+]?\d+)$'      ), lambda s: int(s, 10)),
      (_SCALAR_INT, re.compile(r'^0o(?P<s>[0-7]+)$'      ), lambda s: int(s,  8)),
      (_SCALAR_INT, re.compile(r'^0x(?P<s>[0-9A-Fa-f]+)$'), lambda s: int(s, 16)),

      (_SCALAR_FLOAT, re.compile(r'^\+?\.(?:INF|[Ii]nf)$'), float('inf')),
      (_SCALAR_FLOAT, re.compile(r'^-\.(?:INF|[Ii]nf)$'  ), float('-inf')),
      (_SCALAR_FLOAT, re.compile(r'^\.(?:N[Aa]N|nan)$'   ), float('nan')),
      (_SCALAR_FLOAT, re.compile(r'^(?P<x>[-+]?(?:\.\d+|\d+(?:\.\d*)?)(?:[Ee][-+]?\d+)?)$'), float),

      # See <http://yaml.org/type/timestamp.html>.
      (
         _SCALAR_TIMESTAMP,
         re.compile(r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$'),
         lambda **kwargs: datetime.date(**_make_values_int(kwargs))
      ),
      (
         _SCALAR_TIMESTAMP,
         re.compile(r'''^
            (?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})
            (?:[Tt]|[\t ]+)
            (?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})
            (\.(?P<fraction>\d+))?
            (?:(?:[\t ]*)
               (?P<tz>Z|(?P<tzhour>[-+]\d{1,2})(?::?(?P<tzminute>\d{2}))?)
            )?
         $''', re.VERBOSE),
         _timestamp_to_datetime
      ),
   )
   # Matches a sequence element start.
   _sequence_dash_re = re.compile(r'-(?: +|$)')
   # Characters allowed in a tag.
   _tag_charset = '[-#;/?:@&=+$_.~*\'()0-9A-Za-z]'
   # Matches a tag. This is intentionally an oversimplification of the relatively complex BNF specified by the
   # standard.
   _tag_re = re.compile(r'''
      ^!(?:
         (?P<disable>)|
         (?P<local>''' + _tag_charset + '''+)|
         !(?P<builtin>''' + _tag_charset + '''+)
      )(?:[ ]+|$)
   ''', re.VERBOSE)

   def __init__(self):
      """Constructor."""

      self._reset()

   def _construct_builtin_tag(self, applicable_scalar_types, expected_tag, parsed_text):
      """Constructs a built-in tag by finding a matching pattern in _scalar_tag_conversions and applying the
      corresponding conversion.

      int applicable_scalar_types
         One or more _SCALAR_* constants, activating the matching elements in _scalar_tag_conversions.
      str expected_tag
         Only used if no patterns in the selected _scalar_tag_conversions elements apply: if non-None, this
         string will be reported in the exception raised; if None, parsed_text will be returned without any
         errors.
      str parsed_text
         Parsed scalar to be converted.
      object return
         Converted scalar.
      """

      for scalar_type, matcher, convertor in self._scalar_tag_conversions:
         if scalar_type & applicable_scalar_types:
            match = matcher.match(parsed_text)
            if match:
               if callable(convertor):
                  return convertor(**match.groupdict())
               else:
                  return convertor
      if expected_tag:
         self.raise_parsing_error('expected scalar of type {}'.format(expected_tag))
      else:
         return parsed_text

   def consume_map_implicit(self):
      """Consumes a map.

      dict(str: object) return
         Parsed map.
      """

      old_mapping_min_indent     = self._mapping_min_indent
      old_scalar_wrap_min_indent = self._scalar_wrap_min_indent
      old_sequence_min_indent    = self._sequence_min_indent

      indent = self._line_indent
      self._mapping_min_indent     = indent + 1
      self._scalar_wrap_min_indent = indent + 1
      self._sequence_min_indent    = indent

      ret = {}
      while True:
         # Grab the key and strip off the whole matched string.
         key = self._matched_line.group('key')
         self._line_text = self._line_text[self._matched_line.end():]

         # Parse whatever is left; this may span multiple lines.
         # TODO: reject non-explicit sequences or maps.
         ret[key] = self.consume_object(False)

         # consume_*() functions always quit after reading one last line, so check if we’re still in the map.
         if self._line_text is None or self._line_indent < indent:
            # No next line, or the next line is not part of the map.
            break
         if not self.match_and_store(self._mapping_key_re):
            self.raise_parsing_error('mapping key expected')

      self._mapping_min_indent     = old_mapping_min_indent
      self._scalar_wrap_min_indent = old_scalar_wrap_min_indent
      self._sequence_min_indent    = old_sequence_min_indent
      return ret

   def consume_object(self, allow_implicit_mapping_or_sequence):
      """Dispatches a call to any of the other consume_*() functions, after inspecting the current line.

      bool allow_implicit_mapping_or_sequence
         True if a mapping key or sequence element will be allowed on the initial line, or False otherwise.
      object return
         Parsed object.
      """

      # Save this in case we need to raise errors about the beginning of the object, not its end.
      initial_line_no = self._line_no

      if len(self._line_text) == 0:
         # The current container left no characters on the current line, so read another one.
         if not self.next_line():
            # Nothing at all left in the source.
            return None
         wrapped = True
         allow_implicit_mapping_or_sequence = True
      else:
         wrapped = False

      eof = False
      parsed = ''
      kind = yaml.Kind.SCALAR
      resolve_scalar = True
      tag = None
      expected_kind = None
      # If None, no constructor needs to be called, and the parsed value can be returned as-is.
      constructor = None

      if self.match_and_store(self._tag_re):
         tag = self._matched_line.group()
         # TODO: support more ways of specifying a tag.
         type_s = self._matched_line.lastgroup
         if type_s == 'disable':
            # “!” disables tag resolution, forcing tags to be vanilla (map, seq or str). See YAML 1.2 § 6.9.1.
            # “Node Tags”).
            resolve_scalar = False
         elif type_s == 'local':
            local_tag = self._matched_line.group('local')
            tpl = Parser._local_tags_by_parser_type.get(type(self).__name__, {}).get(local_tag)
            if not tpl:
               self.raise_parsing_error('unrecognized local tag')
            expected_kind, constructor = tpl
         elif type_s == 'builtin':
            builtin_tag = self._matched_line.group('builtin')
            tpl = self._builtin_tags.get(builtin_tag)
            if not tpl:
               self.raise_parsing_error('unrecognized built-in tag')
            expected_kind, constructor = tpl
         else:
            assert(False)

         # Consume the tag.
         match_end = self._matched_line.end()
         if match_end < len(self._line_text):
            # Remove the matched text from the current line.
            self._line_text = self._line_text[match_end:]
            allow_implicit_mapping_or_sequence = False
         else:
            # The whole line was consumed; read a new one.
            eof = not self.next_line()
            wrapped = True
            allow_implicit_mapping_or_sequence = True

      if eof:
         pass
      elif not wrapped and (self._line_text.startswith('"') or self._line_text.startswith('\'')):
         parsed = self.consume_quoted_scalar()
         # According to YAML 1.2 § 6.9.1. “Node Tags”, a quoted scalar is always a string.
         resolve_scalar = False
      elif (
         not wrapped or self._line_indent >= self._sequence_min_indent
      ) and self.match_and_store(self._sequence_dash_re):
         if not allow_implicit_mapping_or_sequence:
            self.raise_parsing_error('sequence element not expected in this context')
         # Continue parsing this line as a sequence.
         parsed = self.consume_sequence_implicit()
         kind = yaml.Kind.SEQUENCE
      elif (
         not wrapped or self._line_indent >= self._mapping_min_indent
      ) and self.match_and_store(self._mapping_key_re):
         if not allow_implicit_mapping_or_sequence:
            self.raise_parsing_error('mapping key not expected in this context')
         # Continue parsing this line as a map.
         parsed = self.consume_map_implicit()
         kind = yaml.Kind.MAPPING
      elif not wrapped or self._line_indent >= self._scalar_wrap_min_indent:
         parsed = self.consume_scalar()
      else:
         # The input was an empty line and the indentation of the next line was incompatible with any of the
         # options above.
         pass

      if constructor:
         # Swap the current line number (which potentially does not refer to parsed anymore) with the initial
         # line number, to provide meaningful error messages.
         final_line_no = self._line_no
         self._line_no = initial_line_no
         if kind is not expected_kind:
            raise TagKindMismatchError('{}:{}: expected {} to construct tag “{}”; found {}'.format(
               self._source_name, self._line_no, expected_kind, tag, kind
            ))
         parsed = constructor(self, parsed)
         # Restore the line number.
         self._line_no = final_line_no
      elif kind is yaml.Kind.SCALAR and resolve_scalar:
         parsed = self._construct_builtin_tag(_SCALAR_ALL, None, parsed)
      return parsed

   def consume_quoted_scalar(self):
      """Consumes a quoted scalar.

      str return
         Parsed scalar.
      """

      quote = self._line_text[0]
      end_quote_index = self._line_text.find(quote, len(quote))
      if end_quote_index > 0:
         ret = ''
      else:
         # The string spans multiple lines; go find its end.
         ret = self._line_text[len(quote):]
         while self.next_line():
            ret += ' '
            end_quote_index = self._line_text.find(quote)
            if end_quote_index >= 0:
               break
            ret += self._line_text
         else:
            self.raise_parsing_error('unexpected end of input while looking for string end quote')
      # Verify that nothing follows the closing quote.
      if not self.match_and_store(self._horizontal_ws_re, end_quote_index + len(quote)):
         self.raise_parsing_error('unexpected characters after string end quote')
      # Consume what we’re returning.
      ret += self._line_text[0 if ret else len(quote):end_quote_index]
      self.next_line()
      return ret

   def consume_scalar(self):
      """Consumes a scalar.

      str return
         Parsed scalar.
      """

      ret = self._line_text
      while self.next_line() and self._line_indent >= self._scalar_wrap_min_indent:
         if ':' in self._line_text:
            self.raise_parsing_error('mapping key not expected in scalar context')
         ret += ' ' + self._line_text
      return ret

   def consume_sequence_implicit(self):
      """Consumes a sequence.

      list(object) return
         Parsed sequence.
      """

      old_mapping_min_indent     = self._mapping_min_indent
      old_scalar_wrap_min_indent = self._scalar_wrap_min_indent
      old_sequence_min_indent    = self._sequence_min_indent

      indent = self._line_indent
      self._scalar_wrap_min_indent = indent + 1

      ret = []
      while True:
         # Strip the “- ” prefix and any following whitespace.
         matched_chars_len = self._matched_line.end()
         self._line_text = self._line_text[matched_chars_len:]
         # The indentation of the sequence element includes the dash match.
         self._line_indent        += matched_chars_len
         self._mapping_min_indent  = indent + matched_chars_len
         self._sequence_min_indent = indent + matched_chars_len

         # Parse whatever is left; this may span multiple lines.
         ret.append(self.consume_object(True))

         # consume_*() functions always quit after reading one last line, so check if we’re still in the
         # sequence.
         if self._line_text is None or self._line_indent < indent:
            break
            # No next line, or the next line is not part of the sequence.
         elif not self.match_and_store(self._sequence_dash_re):
            # The next line is not a sequence element.
            break
         elif self._line_indent > indent:
            self.raise_parsing_error('excessive indentation for sequence element')

      self._mapping_min_indent     = old_mapping_min_indent
      self._scalar_wrap_min_indent = old_scalar_wrap_min_indent
      self._sequence_min_indent    = old_sequence_min_indent
      return ret

   def find_and_consume_doc_start(self):
      """Consumes and validates the start of the YAML document.

      bool return
         True if the current line was wholly consumed, or False if it still contains characters to be
         parsed.
      """

      self.next_line()
      if self._line_text != '%YAML 1.2':
         self.raise_parsing_error('expected %YAML directive')
      if not self.next_line():
         self.raise_parsing_error('missing document start')
      if not self.match_and_store(self._doc_start_re):
         self.raise_parsing_error('expected document start')
      match_end = self._matched_line.end()
      if match_end < len(self._line_text):
         # Remove the matched text from the current line.
         self._line_text = self._line_text[match_end:]
         return False
      else:
         # The whole line was consumed.
         return True

   @classmethod
   def local_tag(cls, tag, kind):
      """Decorator to associate a tag with a constructor. If the constructor is a static function, it will be
      called directly; if it’s a class, a new instance will be constructed with arguments self and parsed,
      respectively the parser itself and the parsed (but not constructed) YAML object.

      str tag
         Tag to associate to the constructor.
      yaml.Kind kind
         Kind expected by the tag’s constructor. If the object being constructed is not of this kind, a syntax
         error will be raised.
      """

      def decorate(constructor):
         cls.register_local_tag(tag, kind, constructor)
         return constructor

      return decorate

   def match_and_store(self, re, start = 0):
      """Performs a match on the current line with the specified regexp, returning True if a match was
      produced and storing the match object for later access via self._matched_line.

      re.RegExp
         Expression to match.
      int start
         Character index from which to start the matching; defaults to 0.
      bool return
         True if re was matched, or False otherwise.
      """

      match = re.match(self._line_text, start)
      self._matched_line = match
      return match != None

   def next_line(self):
      """Attempts to read a new line from the YAML document, making it available as self._line_text after
      stripping from it any indentation, the length of which is stored in self._line_indent.

      bool return
         True if a new line was read, of False otherwise.
      """

      while True:
         self._line_no += 1
         line_text = next(self._lines, None)
         if line_text is None:
            # EOF has no indentation.
            self._line_indent = 0
         else:
            # Strip the trailing line terminator.
            line_text = line_text.rstrip('\n\r')
            # Strip trailing comments.
            # TODO: make this not peek inside quoted strings.
            line_text = self._comment_re.sub('', line_text)
            # If nothing’s left, move on to the next line; otherwise return True to consume it.
            if not line_text:
               continue
            # Determine the indentation of the line.
            self._line_indent = len(self._indent_re.match(line_text).group())
            line_text = line_text[self._line_indent:]
         self._line_text = line_text
         return line_text is not None

   def parse(self, source_name, lines):
      """Parses the specified source.

      str source_name
         Name of the source for use in diagnostic messages.
      iterator(str) lines
         Object that yields YAML lines.
      object return
         Top-level parsed object.
      """

      self._lines = lines
      self._source_name = source_name
      try:
         if self.find_and_consume_doc_start():
            # The whole line was consumed; read the next one.
            if not self.next_line():
               # Nothing follows the document start.
               return None
            o = self.consume_object(True)
         else:
            # Finish reading the line with the document start.
            o = self.consume_object(False)
         # Verify that there’s nothing left to parse.
         if self._line_text is not None:
            self.raise_parsing_error('invalid token')
      finally:
         self._reset()
      return o

   def parse_file(self, file_path):
      """Loads and parses a YAML file.

      str file_path
         Path to the YAML file.
      object return
         Python object corresponding to the contents of the file.
      """

      with io.open(file_path, 'rt', encoding = 'utf-8') as file:
         return self.parse(file_path, file)

   def parse_string(self, s):
      """Parses a string containing YAML.

      str s
         YAML source.
      object return
         Python object corresponding to the contents of the string.
      """

      return self.parse('<string>', iter(s.splitlines(True)))

   def raise_parsing_error(self, message):
      """Raises a yaml.SyntaxError the available context information and the provided message.

      str message
         Error message.
      """

      raise SyntaxError('{}:{}: {}, found: “{}”'.format(
         self._source_name, self._line_no, message, self._line_text
      ))

   @classmethod
   def register_local_tag(cls, tag, kind, constructor):
      """Registers a new local tag, associating it with the specified constructor. If the constructor is a
      static function, it will be called directly; if it’s a class, a new instance will be constructed with
      arguments self and parsed, respectively the parser itself and the parsed (but not constructed) YAML
      object.

      str tag
         Tag to associate to the constructor.
      yaml.Kind kind
         Kind expected by the tag’s constructor. If the object being constructed is not of this kind, a syntax
         error will be raised.
      callable constructor
         Constructor. Must be callable with the signature described above.
      """

      if cls is Parser:
         raise Exception(
            'do not declare/register local tags directly on the Parser class; use a subclass instead'
         )
      local_tags = Parser._local_tags_by_parser_type.setdefault(cls.__name__, {})
      tpl = kind, constructor
      if local_tags.setdefault(tag, tpl) is not tpl:
         raise yaml.DuplicateTagError('local tag “{}” already registered'.format(tag))

   def _reset(self):
      """Reinitializes the internal parser status."""

      self._line_no = 0
      self._matched_line = None
      self._line_text = None
      self._line_indent = 0
      self._lines = None
      self._mapping_min_indent = 0
      self._scalar_wrap_min_indent = 0
      self._sequence_min_indent = 0
      self._sSourceName = '<no input>'

   def _get_source_name(self):
      return self._source_name

   source_name = property(_get_source_name, doc="""
      Returns the name of the source being parsed; e.g. the path to the file.
   """)
