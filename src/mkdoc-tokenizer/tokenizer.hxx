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



////////////////////////////////////////////////////////////////////////////////////////////////////
// mkdoc_tokenizer_app


/*! Characer types. Used to group evolutions by character type, to avoid repetitions: for example,
all evolutions for ‘A’ will always apply to ‘B’.
*/
ABC_ENUM_AUTO_VALUES(char_type,
   bksl,  //! Backslash.
   colon, //! Colon.
   digit, //! Decimal digit.
   dot,   //! Dot.
   eol,   //! End-of-line character.
   fwsl,  //! Forward slash.
   inval, //! Invalid character that can only appear in literals.
   ltr,   //! Letter.
   ltre,  //! Letter ‘e’ or ‘E’.
   minus, //! Minus sign/hyphen.
   plus,  //! Plus sign.
   pound, //! Pound sign/hash.
   punct, //! Punctuation.
   qdbl,  //! Double quotes.
   qsng,  //! Single quote.
   star,  //! Star/asterisk.
   whsp   //! Whitespace.
);

/*! Tokenizer state.
*/
ABC_ENUM_AUTO_VALUES(tokenizer_state,
   bksl, //! Found a single backslash.
   bsac, //! Found a single backslash that may need to be accumulated in the current token.
   bol,  //! Start of a new, non-continued line, with no token. This is the initial (BOF) state.
   cl,   //! Single-quoted character literal.
   cle,  //! Single-quoted character literal, after the closing single-quote.
   cln,  //! Colon.
   cln2, //! Double-colon “::”.
   cmm,  //! Multi-line comment.
   cmms, //! Multi-line comment, after a star (potential terminator sequence start).
   cmmz, //! End of a multi-line comment.
   cms,  //! Single-line comment.
   cpp,  //! C preprocessor directive.
   dot,  //! Single dot.
   dot2, //! Two dots.
   dot3, //! Three dots.
   fwsl, //! Found a single forward slash.
   id,   //! Identifier.
   mns,  //! Minus sign.
   mns2, //! Two minus signs.
   num,  //! Number.
   nume, //! Number followed by ‘e’ or ‘E’ (could be suffix or exponent).
   nums, //! Suffix following a number, or exponent of a number.
   pls,  //! Plus sign.
   pls2, //! Two plus signs.
   punc, //! Other punctuation.
   sl,   //! Double-quoted string literal.
   sle,  //! Double-quoted string literal, after the closing double-quote.
   whsp  //! Whitespace run.
);

/*! Tokenizer action.
*/
ABC_ENUM_AUTO_VALUES(tokenizer_action,
   /*! Accumulate the character into the current token. */
   acc,
   /*! Error; will cause the tokenizer to stop. */
   err,
   /*! Output the current token, then start a new one, ignoring the current character. */
   out,
   /*! Output the current token, then start a new one accumulating the current character into it. */
   o_a,
   /*! Pushe the current state into the state stack. */
   sps,
   /*! Pop from the state stack into the current state. */
   spp,
   /*! Pop from the state stack into the current state, accumulating a backslash and the current
   character into the current token. */
   spb
);

/*! Possible output token types.
*/
ABC_ENUM_AUTO_VALUES(token_type,
   ampersand,
   backslash,
   bracel,
   bracer,
   bracketl,
   bracketr,
   caret,
   charlit,
   comment,
   colon,
   comma,
   cpp_def,
   cpp_flow,
   cpp_incl,
   cpp_other,
   dbl_colon,
   decr,
   ellipsis,
   error,
   document,
   dot,
   equal,
   excl,
   fwdslash,
   gt,
   ident,
   incr,
   less,
   minus,
   number,
   parenl,
   parenr,
   percent,
   pipe,
   plus,
   qmark,
   semicolon,
   stringlit,
   tilde,
   whitesp
);

class tokenizer {
public:

   //! Token.
   class token {
   public:

      /*! Constructor.

      s
         Text of the token.
      */
      token(mstr && s) :
         m_s(std::move(s)),
         m_tt(token_type::error) {
      }

   public:

      //! Token text.
      dmstr m_s;
      //! Token type.
      token_type m_tt;
   };

private:

   /*! Tokenizer evolution.
   */
   struct evo_t {
      tokenizer_state::enum_type stateNext;
      tokenizer_action::enum_type actionNext;
   };

   /*! Token type output for a final state.
   */
   struct output_token_t {
      void (tokenizer::* pfnSpecialCase)(tokenizer_state stateFinal, token * ptk);
      token_type ttFixed;
   };


public:

   /*! Constructor.

   sAll
      String to tokenize.
   */
   tokenizer(mstr && sAll);

   /*! Decomposes m_sAll into a list of tokens.
   */
   void tokenize();

   /*! Determines the output token type for a given comment token.
   */
   void get_comment_token_type(tokenizer_state stateFinal, token * ptk);

   /*! TODO: comment.
   */
   void get_cpreproc_token_type(tokenizer_state stateFinal, token * ptk);

   /*! TODO: comment.
   */
   void get_punctuation_token_type(tokenizer_state stateFinal, token * ptk);


private:

   //! String to tokenize.
   dmstr m_sAll;
   //! Mapping from character values to character types.
   static char_type::enum_type const smc_chtMap[];
   //! Tokenizer evolutions: map from (state, char_type) to (state, action).
   static evo_t const smc_evos[tokenizer_state::size_const][char_type::size_const];
   //! Tokens output by each state when the evolution’s action is “output”.
   static output_token_t const smc_ttStateOutputs[tokenizer_state::size_const];
};

