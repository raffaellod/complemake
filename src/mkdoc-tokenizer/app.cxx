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

/*! Mapping from character values to character types.
*/
static char_type::enum_type const chtMap[128] = {
#define T char_type::
   /*00 */T inval, /*01 */T inval, /*02 */T inval, /*03 */T inval, /*04 */T inval, /*05 */T inval,
   /*06 */T inval, /*\a */T inval, /*08 */T inval, /*\t */T whsp , /*\n */T eol  , /*\v */T whsp ,
   /*\f */T whsp , /*\r */T whsp , /*0e */T inval, /*0f */T inval, /*10 */T inval, /*11 */T inval,
   /*12 */T inval, /*13 */T inval, /*14 */T inval, /*15 */T inval, /*16 */T inval, /*17 */T inval,
   /*18 */T inval, /*19 */T inval, /*0a */T inval, /*\e */T inval, /*1c */T inval, /*1d */T inval,
   /*1e */T inval, /*1f */T inval, /*sp */T whsp , /* ! */T punct, /* " */T qdbl , /* # */T pound,
   /* $ */T inval, /* % */T punct, /* & */T punct, /* ' */T qsng , /* ( */T punct, /* ) */T punct,
   /* * */T star , /* + */T plus , /* , */T punct, /* - */T minus, /* . */T dot  , /* / */T fwsl ,
   /* 0 */T digit, /* 1 */T digit, /* 2 */T digit, /* 3 */T digit, /* 4 */T digit, /* 5 */T digit,
   /* 6 */T digit, /* 7 */T digit, /* 8 */T digit, /* 9 */T digit, /* : */T punct, /* ; */T punct,
   /* < */T punct, /* = */T punct, /* > */T punct, /* ? */T punct, /* @ */T inval, /* A */T ltr  ,
   /* B */T ltr  , /* C */T ltr  , /* D */T ltr  , /* E */T ltre , /* F */T ltr  , /* G */T ltr  ,
   /* H */T ltr  , /* I */T ltr  , /* J */T ltr  , /* K */T ltr  , /* L */T ltr  , /* M */T ltr  ,
   /* N */T ltr  , /* O */T ltr  , /* P */T ltr  , /* Q */T ltr  , /* R */T ltr  , /* S */T ltr  ,
   /* T */T ltr  , /* U */T ltr  , /* V */T ltr  , /* W */T ltr  , /* X */T ltr  , /* Y */T ltr  ,
   /* Z */T ltr  , /* [ */T punct, /* \ */T bksl , /* ] */T punct, /* ^ */T punct, /* _ */T ltr  ,
   /* ` */T inval, /* a */T ltr  , /* b */T ltr  , /* c */T ltr  , /* d */T ltr  , /* e */T ltre ,
   /* f */T ltr  , /* g */T ltr  , /* h */T ltr  , /* i */T ltr  , /* j */T ltr  , /* k */T ltr  ,
   /* l */T ltr  , /* m */T ltr  , /* n */T ltr  , /* o */T ltr  , /* p */T ltr  , /* q */T ltr  ,
   /* r */T ltr  , /* s */T ltr  , /* t */T ltr  , /* u */T ltr  , /* v */T ltr  , /* w */T ltr  ,
   /* x */T ltr  , /* y */T ltr  , /* z */T ltr  , /* { */T punct, /* | */T punct, /* } */T punct,
   /* ~ */T punct, /*7f */T inval
#undef T
};

/*! Tokenizer state.
*/
ABC_ENUM_AUTO_VALUES(state,
   bksl, //! Found a single backslash.
   bsac, //! Found a single backslash that may need to be accumulated in the current token.
   bol,  //! Start of a new, non-continued line, with no token. This is the initial (BOF) state.
   cl,   //! Single-quoted character literal.
   cle,  //! Single-quoted character literal, after the closing single-quote.
   cmm,  //! Multi-line comment.
   cmms, //! Multi-line comment, after a star (potential terminator sequence start).
   cms,  //! Single-line comment.
   cpp,  //! C preprocessor directive.
   dot,  //! Single dot.
   dot2, //! Two dots.
   dot3, //! Three dots.
   fwsl, //! Found a single forward slash.
   id,   //! Identifier.
   mns,  //! Minus sign.
   num,  //! Number.
   nume, //! Number followed by ‘e’ or ‘E’ (could be suffix or exponent).
   nums, //! Suffix following a number, or exponent of a number.
   pls,  //! Plus sign.
   punc, //! Other punctuation.
   sl,   //! Double-quoted string literal.
   sle,  //! Double-quoted string literal, after the closing double-quote.
   whsp  //! Whitespace run.
);

/*! Tokenizer action.
*/
ABC_ENUM_AUTO_VALUES(action,
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

/*! Tokenizer evolution.
*/
struct evo_t {
   state::enum_type stateNext;
   action::enum_type actionNext;
};

/*! Tokenizer evolutions: map from (state, char_type) to (state, action).
*/
static evo_t const evos[state::size_const][char_type::size_const] = {
#define E(s, a) { state::s, action::a }
   /*        bksl        digit       dot         eol         fwsl        inval       ltr         ltre        minus       plus        pound       punct       qdbl        qsng        star        whsp       */
   /*bksl*/ {E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,spp),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err)},
   /*bsac*/ {E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spp),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb)},
   /*bol */ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(bol ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(cpp ,o_a),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(bol ,out)},
   /*cl  */ {E(bsac,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cle ,acc),E(cl  ,acc),E(cl  ,acc)},
   /*cle */ {E(bksl,sps),E(cle ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(cle ,err),E(cle ,acc),E(cle ,acc),E(mns ,o_a),E(pls ,o_a),E(cle ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*cmm */ {E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmms,acc),E(cmm ,acc)},
   /*cmms*/ {E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(fwsl,acc),E(cmms,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmms,acc),E(cmm ,acc)},
   /*cms */ {E(bksl,sps),E(cms ,acc),E(cms ,acc),E(bol ,out),E(cms ,acc),E(cms ,err),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc)},
   /*cpp */ {E(bksl,sps),E(cpp ,acc),E(cpp ,acc),E(bol ,out),E(cpp ,acc),E(cpp ,err),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc)},
   /*dot */ {E(bksl,sps),E(num ,acc),E(dot2,acc),E(bol ,out),E(fwsl,o_a),E(dot ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(mns ,o_a),E(dot ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*dot2*/ {E(bksl,sps),E(dot2,err),E(dot3,acc),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err)},
   /*dot3*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(dot3,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(mns ,o_a),E(dot3,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*fwsl*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(cms ,acc),E(fwsl,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(fwsl,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(cmm ,acc),E(whsp,o_a)},
   /*id  */ {E(bksl,sps),E(id  ,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(id  ,err),E(id  ,acc),E(id  ,acc),E(mns ,o_a),E(pls ,o_a),E(id  ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*mns */ {E(bksl,sps),E(num ,acc),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(mns ,err),E(id  ,o_a),E(id  ,o_a),E(punc,acc),E(pls ,o_a),E(mns ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*num */ {E(bksl,sps),E(num ,acc),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(num ,err),E(nums,acc),E(nume,acc),E(mns ,o_a),E(pls ,o_a),E(num ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*nume*/ {E(bksl,sps),E(nums,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(nume,err),E(nums,acc),E(nums,acc),E(nums,acc),E(nums,acc),E(nume,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*nums*/ {E(bksl,sps),E(nums,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(nums,err),E(nums,acc),E(nums,acc),E(mns ,o_a),E(pls ,o_a),E(nums,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*pls */ {E(bksl,sps),E(num ,o_a),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(pls ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(punc,acc),E(pls ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*punc*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(punc,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*sl  */ {E(bsac,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sle ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc)},
   /*sle */ {E(bksl,sps),E(sle ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(sle ,err),E(sle ,acc),E(sle ,acc),E(mns ,o_a),E(pls ,o_a),E(sle ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,o_a)},
   /*whsp*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(whsp,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(whsp,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(punc,o_a),E(whsp,acc)}
#undef E
};

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
   ellipsis,
   error,
   document,
   dot,
   equal,
   excl,
   fwdslash,
   gt,
   ident,
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

// Forward declaration.
class mkdoc_tokenizer_app;

struct output_token_t {
   token_type (mkdoc_tokenizer_app::* pfnSpecialCase)(state final_state, istr const & sToken);
   token_type ttFixed;
};

class mkdoc_tokenizer_app :
   public app {
public:

   /*! See app::main().
   */
   virtual int main(mvector<istr const> const & vsArgs) {
      ABC_TRACE_FUNC(this, vsArgs);

      dmstr sAll;
      io::text::open_reader(dmstr(ABC_SL("include/abaclade/enum.hxx")))->read_all(&sAll);
      tokenize(sAll);

      return 0;
   }


   /*! TODO: comment.
   */
   void tokenize(istr const & sAll) {
      auto ftwErr(io::text::stderr());

      state stateCurr(state::bol);
      smstr<256> sCurrToken;
      state statePushed;
      for (auto it(sAll.cbegin()); it != sAll.cend(); ++it) {
         char32_t ch(*it);
         // Determine the type of the current character.
         char_type cht;
         if (static_cast<size_t>(ch) < ABC_COUNTOF(chtMap)) {
            cht = chtMap[static_cast<uint8_t>(ch)];
         } else {
            cht = char_type::ltr;
         }

         evo_t const & evo(evos[stateCurr.base()][cht.base()]);
         /*ftwErr->print(
            ABC_SL("evolution: (state: {}, char_type: {} ‘{}’) -> (state: {}, action: {})\n"),
            stateCurr, cht, ch, state(evo.stateNext), action(evo.actionNext)
         );*/

         switch (evo.actionNext) {
            case action::err:
               // Error; will cause the tokenizer to stop.
               ftwErr->write_line(ABC_SL("ERROR"));
               return;
            case action::out:
            case action::o_a:
               if (sCurrToken) {
                  // Determine the output token type for the current final state.
                  output_token_t const & ot(smc_ttStateOutputs[stateCurr.base()]);
                  token_type tt;
                  if (ot.pfnSpecialCase) {
                     tt = (this->*ot.pfnSpecialCase)(stateCurr, sCurrToken);
                  } else {
                     tt = ot.ttFixed;
                  }

                  ftwErr->print(ABC_SL("Token (type: {}): {}\n"), tt, sCurrToken);
               }
               sCurrToken = ABC_SL("");
               if (evo.actionNext != action::o_a) {
                  break;
               }
               // Fall through.
            case action::acc:
               // Accumulate the character into the current token.
               sCurrToken += ch;
               break;
            case action::sps:
               // Pushe the current state into the state stack.
               statePushed = stateCurr;
               break;
            case action::spp:
            case action::spb:
               // Pop from the state stack into the current state.
               stateCurr = statePushed;
               if (evo.actionNext == action::spb) {
                  // Accumulate a backslash and the current character into the current token.
                  sCurrToken += '\\';
                  sCurrToken += ch;
               }
               continue;
         }
         stateCurr = evo.stateNext;
      }
   }


   /*! Determines the output token type for a given comment token.
   */
   token_type get_comment_token_type(state final_state, istr const & sToken) {
      ABC_UNUSED_ARG(final_state);
      // Check for “/*!” and “//!”.
      if (sToken[3] == '!') {
         // Special documentation comment.
         return token_type::document;
      } else {
         return token_type::comment;
      }
   }


   /*! TODO: comment.
   */
   token_type get_cpreproc_token_type(state final_state, istr const & sToken) {
      ABC_UNUSED_ARG(final_state);
      ABC_UNUSED_ARG(sToken);
      return token_type::error;
   }


   /*! TODO: comment.
   */
   token_type get_punctuation_token_type(state final_state, istr const & sToken) {
      ABC_UNUSED_ARG(final_state);
      ABC_UNUSED_ARG(sToken);
      return token_type::error;
   }

private:
   /*! Tokens output by each state when the evolution’s action is “output”. */
   static output_token_t const smc_ttStateOutputs[state::size_const];
};

output_token_t const mkdoc_tokenizer_app::smc_ttStateOutputs[state::size_const] = {
#define OF(fixed)   { nullptr, token_type::fixed }
#define OS(special) { &mkdoc_tokenizer_app::special, token_type::error }
   /* bksl */ OF(backslash),
   /* bsac */ OF(error),
   /* bol  */ OF(error),
   /* cl   */ OF(error),
   /* cle  */ OF(charlit),
   /* cmm  */ OS(get_comment_token_type),
   /* cmms */ OS(get_comment_token_type),
   /* cms  */ OS(get_comment_token_type),
   /* cpp  */ OS(get_cpreproc_token_type),
   /* dot  */ OF(dot),
   /* dot2 */ OF(error),
   /* dot3 */ OF(ellipsis),
   /* fwsl */ OF(fwdslash),
   /* id   */ OF(ident),
   /* mns  */ OF(minus),
   /* num  */ OF(number),
   /* nume */ OF(number),
   /* nums */ OF(number),
   /* pls  */ OF(plus),
   /* punc */ OS(get_punctuation_token_type),
   /* sl   */ OF(error),
   /* sle  */ OF(stringlit),
   /* whsp */ OF(whitesp)
#undef OF
#undef OS
};

ABC_APP_CLASS(mkdoc_tokenizer_app)

