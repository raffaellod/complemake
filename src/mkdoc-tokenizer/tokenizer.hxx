﻿/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

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

#ifndef _TOKENIZER_HXX
#define _TOKENIZER_HXX

#include <lofty.hxx>
#ifdef LOFTY_CXX_PRAGMA_ONCE
   #pragma once
#endif
#include <lofty/app.hxx>
#include <lofty/io/text/file.hxx>


////////////////////////////////////////////////////////////////////////////////////////////////////
// Globals

/*! Characer types. Used to group evolutions by character type, to avoid repetitions: for example,
all evolutions for ‘A’ will always apply to ‘B’. */
LOFTY_ENUM_AUTO_VALUES(char_type,
   amp,   //! Ampersand.
   aster, //! Asterisk/star.
   bksl,  //! Backslash.
   caret, //! Caret.
   colon, //! Colon.
   digit, //! Decimal digit.
   dot,   //! Dot.
   eol,   //! End-of-line character.
   equal, //! Equal sign.
   excl,  //! Exclamation point.
   fwsl,  //! Forward slash.
   gt,    //! Greater-than sign.
   inval, //! Invalid character that can only appear in literals.
   lt,    //! Less-than sign.
   ltr,   //! Letter.
   ltre,  //! Letter ‘e’ or ‘E’.
   minus, //! Minus sign/hyphen.
   perc,  //! Percent sign.
   pipe,  //! Pipe/vertical bar.
   plus,  //! Plus sign.
   pound, //! Pound sign/hash.
   punct, //! Punctuation.
   qdbl,  //! Double quotes.
   qsng,  //! Single quote.
   tilde, //! Tilde.
   whsp   //! Whitespace.
);

//! Tokenizer state.
LOFTY_ENUM_AUTO_VALUES(tokenizer_state,
   amp,  //! Ampersand.
   amp2, //! Two ampersands.
   arw,  //! Arrow “->”.
   arwa, //! Arrow followed by an asterisk “->*”.
   astr, //! Asterisk/star.
   bksl, //! Single backslash.
   bsac, //! Single backslash that may need to be accumulated in the current token.
   bol,  //! Start of a new, non-continued line, with no token. This is the initial (BOF) state.
   cl,   //! Single-quoted character literal.
   cle,  //! Single-quoted character literal, after the closing single-quote.
   cln,  //! Colon.
   cln2, //! Double-colon “::”.
   cmm,  //! Multi-line comment.
   cmms, //! Multi-line comment, after an asterisk (potential terminator sequence start).
   cmmz, //! End of a multi-line comment.
   cms,  //! Single-line comment.
   cpp,  //! C preprocessor directive.
   crt,  //! Caret.
   crt2, //! Two carets.
   dot,  //! Single dot.
   dot2, //! Two dots.
   dot3, //! Three dots.
   dota, //! Dot followed by an asterisk.
   eql,  //! Equal sign.
   excl, //! Exclamation point.
   fwsl, //! Single forward slash.
   gt,   //! Greater-than sign.
   gt2,  //! TwoGreater-than signs.
   id,   //! Identifier.
   lt,   //! Less-than sign.
   lt2,  //! Two less-than signs.
   mns,  //! Minus sign.
   mns2, //! Two minus signs.
   num,  //! Number.
   nume, //! Number followed by ‘e’ or ‘E’ (could be suffix or exponent).
   nums, //! Suffix following a number, or exponent of a number.
   opeq, //! Operator followed by an equal sign.
   perc, //! Percent sign.
   pip,  //! Pipe/vertical bar.
   pip2, //! Two pipes/vertical bars.
   pls,  //! Plus sign.
   pls2, //! Two plus signs.
   punc, //! Other punctuation.
   sl,   //! Double-quoted string literal.
   sle,  //! Double-quoted string literal, after the closing double-quote.
   tild, //! Tilde.
   whsp  //! Whitespace run.
);

//! Tokenizer action.
LOFTY_ENUM_AUTO_VALUES(tokenizer_action,
   //! Accumulate the character into the current token.
   accumulate,
   //! Error; will cause the tokenizer to stop.
   error,
   //! Pop from the state stack into the current state.
   pop_state,
   /*! Pop from the state stack into the current state, accumulating a backslash and the current
   character into the current token.
   */
   pop_state_and_accumulate_backslash,
   //! Pushes the current state into the state stack.
   push_state,
   //! Yield the current token, then start a new one accumulating the current character into it.
   yield_and_accumulate,
   //! Yield the current token, then start a new one, ignoring the current character.
   yield_and_ignore
);

//! Possible output token types.
LOFTY_ENUM_AUTO_VALUES(token_type,
   ampersand,
   assign,
   asterisk,
   bracel,
   bracer,
   bracketl,
   bracketr,
   charlit,
   comment,
   colon,
   comma,
   cpp_def,
   cpp_flow,
   cpp_incl,
   cpp_other,
   dbl_colon,
   ellipsis,
   error,
   document,
   dot,
   end,               //! EOF with no associated token text.
   identifier,
   minus,
   number,
   op_add_assign,
   op_bit_and,
   op_bit_and_assign,
   op_bit_not,
   op_bit_or,
   op_bit_or_assign,
   op_bit_xor,
   op_bit_xor_assign,
   op_decr,
   op_deref_member_access,
   op_div,
   op_div_assign,
   op_incr,
   op_log_and,
   op_log_not,
   op_log_or,
   op_log_xor,
   op_lsh,
   op_lsh_assign,
   op_mod,
   op_mod_assign,
   op_mult_assign,
   op_ptr_to_member_deref_val,
   op_ptr_to_member_deref_ptr,
   op_rel_equal,
   op_rel_noteq,
   op_rel_gt,
   op_rel_gteq,
   op_rel_lt,
   op_rel_lteq,
   op_rsh,
   op_rsh_assign,
   op_sub_assign,
   parenl,
   parenr,
   plus,
   qmark,
   semicolon,
   stringlit,
   whitesp
);

////////////////////////////////////////////////////////////////////////////////////////////////////
// token

//! Token.
class token {
public:
   /*! Constructor.

   s
      Text of the token.
   */
   token() :
      m_tt(token_type::error) {
   }
   explicit token(token_type tt) :
      m_tt(tt) {
   }
   explicit token(lofty::mstr && s) :
      m_s(std::move(s)),
      m_tt(token_type::error) {
   }
   token(token && tk) :
      m_s(std::move(tk.m_s)),
      m_tt(std::move(tk.m_tt)) {
   }

   /*! Assignment operator.

   tk
      Source token.
   return
      *this.
   */
   token & operator=(token && tk) {
      m_s = std::move(tk.m_s);
      m_tt = std::move(tk.m_tt);
      return *this;
   }

public:
   //! Token text.
   lofty::dmstr m_s;
   //! Token type.
   token_type m_tt;
};

////////////////////////////////////////////////////////////////////////////////////////////////////
// token_iterator

//! Iterates over the C++ tokens in a string.
class token_iterator {
private:
   friend token_iterator const & token_iterator_end();

   //! Tokenizer evolution.
   struct evo_t {
      tokenizer_state::enum_type stateNext;
      tokenizer_action::enum_type actionNext;
   };

   //! Token type output for a final state.
   struct output_token_t {
      void (token_iterator::* pfnSpecialCase)();
      token_type ttFixed;
   };

public:
   /*! Constructor.

   sAll
      String to tokenize.
   */
   explicit token_iterator(lofty::mstr && sAll);

   /*! Dereferencing operator.

   return
      Reference to the current token.
   */
   token const & operator*() const {
      return m_tkCurr;
   }

   /*! Pre-increment operator.

   return
      *this.
   */
   token_iterator & operator++();

   /*! Equality relational operator.

   it
      Object to compare to *this.
   return
      true if both *this and it are unable to yield any more tokens, or false otherwise.
   */
   bool operator==(token_iterator const & it) const {
      return m_tkCurr.m_tt == token_type::end && it.m_tkCurr.m_tt == token_type::end;
   }

   /*! Inequality relational operator.

   it
      Object to compare to *this.
   return
      true if *this or it can still yield tokens, or false otherwise.
   */
   bool operator!=(token_iterator const & it) const {
      return !operator==(it);
   }

private:
   /*! Constructor. Used internally to generate token_iterator constants.

   tt
      Initial token type.
   */
   token_iterator(token_type tt) :
      m_tkCurr(tt) {
   }

   //! Finalizes the current token, allowing to yield it.
   void finalize_next_token();

   //! Determines the output token type for the current comment token.
   void get_comment_token_type();

   //! Determines the output token type for the current compound assignment operator token.
   void get_compound_assignm_token_type();

   //! Determines the output token type for the current C preprocessor token.
   void get_cpreproc_token_type();

   //! Determines the output token type for the current punctuation token.
   void get_punctuation_token_type();

private:
   //! String to tokenize.
   lofty::dmstr m_sAll;
   //! Iterator to the current character in m_sAll.
   lofty::dmstr::const_iterator m_itAllCurr;
   //! Current state of the tokenizer.
   tokenizer_state m_stateCurr;
   //! Current token.
   token m_tkCurr;
   /*! Next token, potentially written by a different thread while the client’s thread consumes
   m_tkCurr. */
   token m_tkNext;
   //! Mapping from character values to character types.
   static char_type::enum_type const smc_chtMap[];
   //! Tokenizer evolutions: map from (state, char_type) to (state, action).
   static evo_t const smc_evos[tokenizer_state::size_const][char_type::size_const];
   //! Tokens output by each state when the evolution’s action is “output”.
   static output_token_t const smc_ttStateOutputs[tokenizer_state::size_const];
   //! Iterator in final state.
   static token_iterator const smc_itEnd;
};

//! Returns an “end” iterator.
inline token_iterator const & token_iterator_end() {
   return token_iterator::smc_itEnd;
}

////////////////////////////////////////////////////////////////////////////////////////////////////

#endif //_TOKENIZER_HXX
