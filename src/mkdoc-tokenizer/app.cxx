/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

Copyright 2014
Raffaello D. Di Napoli

This file is part of Abaclade.

Abaclade is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Abaclade is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along with Abaclade. If not, see
<http://www.gnu.org/licenses/>.
--------------------------------------------------------------------------------------------------*/

#include <abaclade.hxx>
#include <abaclade/app.hxx>
#include <abaclade/io/text/file.hxx>
using namespace abc;

#include "tokenizer.hxx"



////////////////////////////////////////////////////////////////////////////////////////////////////
// mkdoc_tokenizer_app


class mkdoc_tokenizer_app :
   public app {
public:

   /*! See app::main().
   */
   virtual int main(mvector<istr const> const & vsArgs) {
      ABC_TRACE_FUNC(this, vsArgs);

      dmstr sAll;
      io::text::open_reader(dmstr(ABC_SL("include/abaclade/enum.hxx")))->read_all(&sAll);
      tokenizer tk(std::move(sAll));
      tk.tokenize();

      return 0;
   }
};

ABC_APP_CLASS(mkdoc_tokenizer_app)

