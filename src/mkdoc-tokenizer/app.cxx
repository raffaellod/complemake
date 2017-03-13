/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

Copyright 2014, 2017 Raffaello D. Di Napoli

This file is part of Complemake.

Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU 
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along with Complemake. If not, see
<http://www.gnu.org/licenses/>.
--------------------------------------------------------------------------------------------------*/

#include <lofty.hxx>
#include <lofty/app.hxx>
#include <lofty/io/text/file.hxx>

#include "tokenizer.hxx"
#include "parser.hxx"


////////////////////////////////////////////////////////////////////////////////////////////////////
// mkdoc_tokenizer_app

class mkdoc_tokenizer_app : public lofty::app {
public:
   //! See app::main().
   virtual int main(lofty::mvector<lofty::istr const> const & vsArgs) {
      LOFTY_TRACE_FUNC(this, vsArgs);

      auto ftwErr(lofty::io::text::stderr());

      lofty::dmstr sAll;
      lofty::io::text::open_reader(
         lofty::dmstr(LOFTY_SL("../../../lofty/include/lofty/enum.hxx"))
      )->read_all(&sAll);
      for (token_iterator it(std::move(sAll)); it != token_iterator_end(); ++it) {
         token const & tk = *it;
         ftwErr->print(LOFTY_SL("\033[35;1mToken:\033[0m (type: {}): “{}”\n"), tk.m_tt, tk.m_s);
      }

      return 0;
   }
};

LOFTY_APP_CLASS(mkdoc_tokenizer_app)
