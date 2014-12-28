/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

Copyright 2014
Raffaello D. Di Napoli

This file is part of Abamake.

Abamake is free software: you can redistribute it and/or modify it under the terms of the GNU 
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Abamake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along with Abamake. If not, see
<http://www.gnu.org/licenses/>.
--------------------------------------------------------------------------------------------------*/

#include <abaclade.hxx>
#include <abaclade/app.hxx>
#include <abaclade/io/text/file.hxx>

#include "tokenizer.hxx"
#include "parser.hxx"


////////////////////////////////////////////////////////////////////////////////////////////////////
// mkdoc_tokenizer_app

class mkdoc_tokenizer_app : public abc::app {
public:
   //! See app::main().
   virtual int main(abc::mvector<abc::istr const> const & vsArgs) {
      ABC_TRACE_FUNC(this, vsArgs);

      auto ftwErr(abc::io::text::stderr());

      abc::dmstr sAll;
      abc::io::text::open_reader(abc::dmstr(ABC_SL("include/abaclade/enum.hxx")))->read_all(&sAll);
      for (token_iterator it(std::move(sAll)); it != token_iterator_end(); ++it) {
         token const & tk = *it;
         ftwErr->print(ABC_SL("\033[35;1mToken:\033[0m (type: {}): “{}”\n"), tk.m_tt, tk.m_s);
      }

      return 0;
   }
};

ABC_APP_CLASS(mkdoc_tokenizer_app)
